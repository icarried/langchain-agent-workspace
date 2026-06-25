from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .chunking import chunk_elements
from .llm import MODEL_CONFIGS
from .prompts import (
    CANDIDATE_DECISION_HUMAN,
    CANDIDATE_DECISION_SYSTEM,
    CHUNK_REVIEW_HUMAN,
    CHUNK_REVIEW_SYSTEM,
)
from .reference_loader import load_university_references
from .resume_loader import load_resume_elements, resume_source_filename
from .schemas import BatchResumeReviewState, CandidateDecision, CandidateResume
from .security import find_prompt_injections


SOFT_PROFICIENCY_TERMS = ("熟练", "熟悉", "了解", "掌握", "精通", "擅长")
TECHNICAL_SKILL_TERMS = (
    "python",
    "java",
    "c++",
    "c#",
    "golang",
    "rust",
    "sql",
    "pytorch",
    "tensorflow",
    "docker",
    "kubernetes",
    "机器学习",
    "深度学习",
    "大模型",
    "rag",
    "计算机视觉",
    "强化学习",
    "编程语言",
    "开发框架",
    "技术工具",
)
NAME_SECTION_TITLES = {
    "个人信息",
    "基本信息",
    "联系方式",
    "求职意向",
    "教育背景",
    "教育经历",
    "工作经历",
    "项目经历",
    "专业技能",
    "技能",
    "简历",
}
NON_NAME_MARKERS = (
    "本科",
    "硕士",
    "博士",
    "大专",
    "专科",
    "大学",
    "学院",
    "工程师",
    "项目",
    "经历",
    "技能",
    "教育",
    "工作",
    "求职",
)


def build_graph(llm: Any | None = None):
    graph = StateGraph(BatchResumeReviewState)
    graph.add_node("load_inputs", _load_inputs)
    graph.add_node("split_resumes", _split_resumes)
    graph.add_node("review_candidate_chunks", _review_candidate_chunks(llm))
    graph.add_node("decide_candidates", _decide_candidates(llm))
    graph.add_node("filter_and_rank", _filter_and_rank)
    graph.add_node("aggregate_report", _aggregate_report)
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "split_resumes")
    graph.add_edge("split_resumes", "review_candidate_chunks")
    graph.add_edge("review_candidate_chunks", "decide_candidates")
    graph.add_edge("decide_candidates", "filter_and_rank")
    graph.add_edge("filter_and_rank", "aggregate_report")
    graph.add_edge("aggregate_report", END)
    return graph.compile()


def _load_inputs(state: BatchResumeReviewState) -> BatchResumeReviewState:
    candidates: list[CandidateResume] = []
    for index, resume_path in enumerate(state["resume_paths"], start=1):
        try:
            filename = resume_source_filename(resume_path)
        except ValueError as exc:
            filename = f"remote-resume-{index:03d}"
            filename_error = str(exc)
        else:
            filename_error = ""
        candidate = CandidateResume(
            candidate_id=f"candidate-{index:03d}",
            filename=filename,
            path=resume_path,
        )
        try:
            if filename_error:
                raise ValueError(filename_error)
            candidate.elements = load_resume_elements(resume_path)
            candidate.candidate_name = extract_candidate_name(candidate.elements, candidate.filename)
        except (FileNotFoundError, OSError, ValueError) as exc:
            candidate.load_error = str(exc)
        candidates.append(candidate)

    return {
        **state,
        "candidates": candidates,
        "job_description": _read_job_description(state),
        "review_guide": _read_required(state.get("review_guide_path")),
        "university_reference": load_university_references(),
    }


def _split_resumes(state: BatchResumeReviewState) -> BatchResumeReviewState:
    provider = state.get("provider", "deepseek")
    max_chars = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"]).practical_chunk_chars
    candidates = state.get("candidates", [])
    for candidate in candidates:
        if not candidate.load_error:
            candidate.chunks = chunk_elements(candidate.elements, max_chars=max_chars)
            if not candidate.chunks:
                candidate.load_error = "resume contains no reviewable content"
    return {**state, "candidates": candidates}


def _review_candidate_chunks(llm: Any | None):
    def node(state: BatchResumeReviewState) -> BatchResumeReviewState:
        findings: dict[str, list[str]] = {
            candidate.candidate_id: [] for candidate in state.get("candidates", [])
        }
        if state.get("dry_run", False) or llm is None:
            for candidate in state.get("candidates", []):
                if candidate.load_error:
                    findings[candidate.candidate_id].append(f"解析失败: {candidate.load_error}")
                    continue
                for chunk in candidate.chunks:
                    findings[candidate.candidate_id].append(
                        f"{chunk.chunk_id}: 已解析元素 {chunk.start_element}-{chunk.end_element}，"
                        f"字符数 {chunk.char_count}。"
                    )
            return {**state, "chunk_findings": findings}

        prompt = ChatPromptTemplate.from_messages(
            [("system", CHUNK_REVIEW_SYSTEM), ("human", CHUNK_REVIEW_HUMAN)]
        )
        chain = prompt | llm | StrOutputParser()
        jobs: dict[Any, tuple[str, str]] = {}
        candidates = state.get("candidates", [])
        chunk_count = sum(len(candidate.chunks) for candidate in candidates)
        with ThreadPoolExecutor(max_workers=min(8, max(1, chunk_count))) as executor:
            for candidate in candidates:
                for chunk in candidate.chunks:
                    future = executor.submit(
                        chain.invoke,
                        {
                            "candidate_id": candidate.candidate_id,
                            "candidate_name": candidate.candidate_name,
                            "filename": candidate.filename,
                            "chunk_id": chunk.chunk_id,
                            "title": chunk.title,
                            "start_element": chunk.start_element,
                            "end_element": chunk.end_element,
                            "chunk_text": chunk.text,
                            "job_description": state.get("job_description", ""),
                            "review_guide": state.get("review_guide", ""),
                        },
                    )
                    jobs[future] = (candidate.candidate_id, chunk.chunk_id)

            for future in as_completed(jobs):
                candidate_id, chunk_id = jobs[future]
                try:
                    finding = future.result()
                except Exception as exc:  # A single model failure must not abort the batch.
                    finding = f"{chunk_id}: 模型审查失败，需人工确认: {exc}"
                findings[candidate_id].append(finding)

        return {**state, "chunk_findings": findings}

    return node


def _decide_candidates(llm: Any | None):
    def node(state: BatchResumeReviewState) -> BatchResumeReviewState:
        candidates = state.get("candidates", [])
        if state.get("dry_run", False) or llm is None:
            decisions = [
                CandidateDecision(
                    candidate_id=candidate.candidate_id,
                    filename=candidate.filename,
                    candidate_name=candidate.candidate_name or Path(candidate.filename).stem,
                    status="pending_review",
                    score=None,
                    summary="dry-run 仅验证解析和工作流，未调用模型执行筛选或评分。",
                    risks=[candidate.load_error] if candidate.load_error else [],
                )
                for candidate in candidates
            ]
            return {**state, "decisions": decisions}

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CANDIDATE_DECISION_SYSTEM),
                ("human", CANDIDATE_DECISION_HUMAN),
            ]
        )
        chain = prompt | llm | StrOutputParser()
        decisions_by_id: dict[str, CandidateDecision] = {}
        jobs: dict[Any, CandidateResume] = {}
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(candidates)))) as executor:
            for candidate in candidates:
                if candidate.load_error:
                    decisions_by_id[candidate.candidate_id] = _pending_decision(
                        candidate,
                        f"简历解析失败: {candidate.load_error}",
                    )
                    continue
                findings = state.get("chunk_findings", {}).get(candidate.candidate_id, [])
                future = executor.submit(
                    chain.invoke,
                    {
                        "candidate_id": candidate.candidate_id,
                        "candidate_name": candidate.candidate_name,
                        "filename": candidate.filename,
                        "job_description": state.get("job_description", ""),
                        "review_guide": state.get("review_guide", ""),
                        "university_reference": state.get("university_reference", ""),
                        "chunk_findings": "\n\n".join(findings),
                    },
                )
                jobs[future] = candidate

            for future in as_completed(jobs):
                candidate = jobs[future]
                try:
                    decisions_by_id[candidate.candidate_id] = parse_candidate_decision(
                        future.result(), candidate, state.get("job_description", "")
                    )
                except Exception as exc:  # Preserve other candidate results.
                    decisions_by_id[candidate.candidate_id] = _pending_decision(
                        candidate,
                        f"候选人决策失败: {exc}",
                    )

        decisions = [decisions_by_id[candidate.candidate_id] for candidate in candidates]
        return {**state, "decisions": decisions}

    return node


def parse_candidate_decision(
    raw: str,
    candidate: CandidateResume,
    job_description: str = "",
) -> CandidateDecision:
    payload = _parse_json_object(raw)
    status = str(payload.get("status", "pending_review")).strip().lower()
    if status not in {"qualified", "excluded", "pending_review"}:
        status = "pending_review"

    normalized_requirements = _normalize_hard_requirements(payload.get("hard_requirements"))
    soft_requirements = []
    for item in normalized_requirements:
        requirement = item["requirement"]
        if _is_soft_skill_requirement(requirement):
            soft_requirements.append(item)
        elif _is_education_requirement(requirement) and not _has_explicit_education_gate(
            job_description
        ):
            soft_requirements.append(item)
    hard_requirements = [item for item in normalized_requirements if item not in soft_requirements]
    exclusion_reasons = _string_list(payload.get("exclusion_reasons"))
    gaps = _string_list(payload.get("gaps"))
    risks = _string_list(payload.get("risks"))
    for item in soft_requirements:
        if item["status"] != "met":
            category = (
                "技能匹配评分项" if _is_soft_skill_requirement(item["requirement"]) else "教育背景评分项"
            )
            gap = f"{category}（非硬筛）：{item['requirement']}；{item['evidence']}"
            if gap not in gaps:
                gaps.append(gap)

    not_met = [item for item in hard_requirements if item["status"] == "not_met"]
    uncertain = [item for item in hard_requirements if item["status"] == "uncertain"]
    injections = detect_prompt_injections(candidate)
    if injections:
        status = "excluded"
        for evidence in injections:
            reason = f"发现提示词注入，按招聘规则筛除：{evidence}"
            if reason not in exclusion_reasons:
                exclusion_reasons.append(reason)
            if evidence not in risks:
                risks.append(evidence)
    elif not_met:
        status = "excluded"
        for item in not_met:
            reason = f"{item['requirement']}: {item['evidence']}"
            if reason not in exclusion_reasons:
                exclusion_reasons.append(reason)
    elif status == "qualified" and uncertain:
        status = "pending_review"
    elif status == "excluded":
        status = "pending_review"

    score = (
        _normalize_score(payload.get("score"))
        if status in {"qualified", "pending_review"}
        else None
    )
    if status == "qualified" and score is None:
        status = "pending_review"
    return CandidateDecision(
        candidate_id=candidate.candidate_id,
        filename=candidate.filename,
        candidate_name=candidate.candidate_name or Path(candidate.filename).stem,
        status=status,
        score=score,
        summary=str(payload.get("summary") or "未提供候选人摘要。").strip(),
        hard_requirements=hard_requirements,
        exclusion_reasons=exclusion_reasons,
        strengths=_string_list(payload.get("strengths")),
        gaps=gaps,
        risks=risks,
        interview_questions=_string_list(payload.get("interview_questions")),
    )


def extract_candidate_name(elements: list[Any], filename: str) -> str:
    for element in elements[:30]:
        text = _clean_resume_line(element.text)
        match = re.match(r"^(?:姓名|候选人姓名)\s*[:：]\s*(.+)$", text)
        if match:
            name = _clean_name(match.group(1))
            if name:
                return name

    for element in elements[:12]:
        raw_text = element.text.strip()
        text = _clean_resume_line(element.text)
        if text in NAME_SECTION_TITLES or any(marker in text for marker in ("@", "电话", "邮箱")):
            continue
        if any(marker in text for marker in NON_NAME_MARKERS):
            continue
        if re.search(r"\d{4}[.年/-]", text) or ":" in text or "：" in text:
            continue
        name = _clean_name(text)
        is_markdown_heading = raw_text.startswith("#")
        is_short_chinese_name = 2 <= len(name) <= 8 and re.fullmatch(r"[\u4e00-\u9fff·]+", name)
        is_heading_name = is_markdown_heading and 2 <= len(name) <= 30
        if is_short_chinese_name or is_heading_name:
            return name
    return Path(filename).stem


def detect_prompt_injections(candidate: CandidateResume) -> list[str]:
    return find_prompt_injections(candidate.elements)


def partition_and_rank(
    decisions: list[CandidateDecision],
) -> tuple[list[CandidateDecision], list[CandidateDecision], list[CandidateDecision]]:
    rankable = [
        decision
        for decision in decisions
        if decision.status in {"qualified", "pending_review"} and decision.score is not None
    ]
    rankable.sort(key=lambda item: (-(item.score or 0), item.candidate_id))
    ranked = [replace(decision, rank=index) for index, decision in enumerate(rankable, start=1)]
    excluded = [decision for decision in decisions if decision.status == "excluded"]
    pending = [decision for decision in decisions if decision.status == "pending_review"]
    return ranked, excluded, pending


def _filter_and_rank(state: BatchResumeReviewState) -> BatchResumeReviewState:
    ranked, excluded, pending = partition_and_rank(state.get("decisions", []))
    return {
        **state,
        "ranked_candidates": ranked,
        "excluded_candidates": excluded,
        "pending_candidates": pending,
    }


def _aggregate_report(state: BatchResumeReviewState) -> BatchResumeReviewState:
    report = render_batch_report(state)
    output_path = state.get("output_path")
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    return {**state, "final_report": report}


def render_batch_report(state: BatchResumeReviewState) -> str:
    candidates = state.get("candidates", [])
    ranked = state.get("ranked_candidates", [])
    excluded = state.get("excluded_candidates", [])
    pending = state.get("pending_candidates", [])
    ranked_pending_count = sum(item.status == "pending_review" for item in ranked)
    unranked_pending = [item for item in pending if item.score is None]
    rank_by_id = {item.candidate_id: item.rank for item in ranked}
    dry_run = state.get("dry_run", False)
    lines = [
        "# 批量简历审查与排序报告",
        "",
        "## 批次概况",
        "",
        f"- 输入简历: {len(candidates)} 份",
        f"- 参与排名: {len(ranked)} 人",
        f"- 其中需人工复核: {ranked_pending_count} 人",
        f"- 筛除: {len(excluded)} 人",
        f"- 未完成评分的复核项: {len(unranked_pending)} 人",
        f"- 运行模式: {'dry-run（未调用模型）' if dry_run else '正式审查'}",
        "- 高校参考资料: 已加载教育部 985/211、2022 第二轮双一流名单及动态查询规则。",
        "- 排序约束: 筛除候选人不参与排序；证据待确认者保留排名并附加复核标记。",
        "",
        "## 候选人排序",
        "",
    ]
    if ranked:
        lines.extend(
            [
                "| 排名 | 候选人 | 文件 | 得分 | 复核 | 摘要 |",
                "| ---: | --- | --- | ---: | --- | --- |",
            ]
        )
        for decision in ranked:
            lines.append(
                f"| {decision.rank} | {_cell(decision.candidate_name)} | "
                f"{_cell(decision.filename)} | {decision.score} | "
                f"{'需复核' if decision.status == 'pending_review' else '-'} | "
                f"{_cell(decision.summary)} |"
            )
    else:
        lines.append("无候选人进入排序。")

    lines.extend(["", "## 筛除名单", ""])
    if excluded:
        lines.extend(["| 候选人 | 文件 | 筛除理由 |", "| --- | --- | --- |"])
        for decision in excluded:
            lines.append(
                f"| {_cell(decision.candidate_name)} | {_cell(decision.filename)} | "
                f"{_cell('；'.join(decision.exclusion_reasons))} |"
            )
    else:
        lines.append("无明确筛除候选人。")

    lines.extend(["", "## 附加复核项", ""])
    if pending:
        lines.extend(
            [
                "| 候选人 | 文件 | 排名 | 复核原因或风险 |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for decision in pending:
            reason = "；".join(decision.risks + decision.gaps) or decision.summary
            lines.append(
                f"| {_cell(decision.candidate_name)} | {_cell(decision.filename)} | "
                f"{rank_by_id.get(decision.candidate_id) or '未评分'} | {_cell(reason)} |"
            )
    else:
        lines.append("无附加复核项。")

    lines.extend(["", "## 候选人详情", ""])
    ranked_ids = {item.candidate_id for item in ranked}
    ordered = ranked + excluded + [item for item in pending if item.candidate_id not in ranked_ids]
    for decision in ordered:
        lines.extend(_decision_detail(decision))
    return "\n".join(lines).rstrip() + "\n"


def _decision_detail(decision: CandidateDecision) -> list[str]:
    status_label = {
        "qualified": "通过筛选",
        "excluded": "筛除",
        "pending_review": (
            "参与排名（需人工复核）" if decision.rank is not None else "未完成评分（需人工复核）"
        ),
    }[decision.status]
    lines = [
        f"### {decision.candidate_id} {decision.candidate_name}",
        "",
        f"- 文件: {decision.filename}",
        f"- 状态: {status_label}",
        f"- 得分: {decision.score if decision.score is not None else '未完成评分'}",
        f"- 摘要: {decision.summary}",
    ]
    sections = [
        ("筛除理由", decision.exclusion_reasons),
        ("优势", decision.strengths),
        ("差距", decision.gaps),
        ("风险", decision.risks),
        ("面试追问", decision.interview_questions),
    ]
    for title, items in sections:
        if items:
            lines.extend(["", f"**{title}**"])
            lines.extend(f"- {item}" for item in items)
    lines.append("")
    return lines


def _read_job_description(state: BatchResumeReviewState) -> str:
    text = (state.get("job_description_text") or "").strip()
    if text:
        return text
    path = state.get("job_description_path")
    if not path:
        raise ValueError("job description is required for batch screening and ranking")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"job description file not found: {p}")
    text = p.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("job description must not be empty")
    return text


def _read_required(path: str | None) -> str:
    if not path:
        raise ValueError("review guide path is required")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"review guide file not found: {p}")
    return p.read_text(encoding="utf-8-sig")


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response does not contain a JSON object")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("candidate decision must be a JSON object")
    return payload


def _normalize_hard_requirements(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    results = []
    for item in value:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "uncertain")).strip().lower()
        if status not in {"met", "not_met", "uncertain"}:
            status = "uncertain"
        results.append(
            {
                "requirement": str(item.get("requirement", "未命名硬性条件")).strip(),
                "status": status,
                "evidence": str(item.get("evidence", "未提供证据")).strip(),
            }
        )
    return results


def _is_soft_skill_requirement(requirement: str) -> bool:
    lowered = requirement.lower()
    if any(term in requirement for term in SOFT_PROFICIENCY_TERMS):
        return True
    has_skill = any(term in lowered for term in TECHNICAL_SKILL_TERMS)
    has_experience_gate = "经验" in requirement or bool(
        re.search(r"(?:至少|不低于)?\s*[一二三四五六七八九十\d]+\s*年", requirement)
    )
    return has_skill and not has_experience_gate


def _is_education_requirement(requirement: str) -> bool:
    return any(term in requirement for term in ("学历", "本科", "学士", "硕士", "研究生", "博士"))


def _has_explicit_education_gate(job_description: str) -> bool:
    return bool(
        re.search(
            r"(?:要求|最低|必须|须|需).{0,24}(?:大专|专科|本科|学士|硕士|研究生|博士)"
            r"|(?:大专|专科|本科|学士|硕士|研究生|博士).{0,12}(?:及以上|以上学历|起)",
            job_description,
            re.IGNORECASE,
        )
    )


def _clean_resume_line(value: str) -> str:
    return re.sub(r"^[#>*\-\s]+", "", value).strip()


def _clean_name(value: str) -> str:
    return re.sub(r"[（(].*$", "", value).strip(" #*：:，,;；")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_score(value: Any) -> int | None:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def _pending_decision(candidate: CandidateResume, reason: str) -> CandidateDecision:
    return CandidateDecision(
        candidate_id=candidate.candidate_id,
        filename=candidate.filename,
        candidate_name=candidate.candidate_name or Path(candidate.filename).stem,
        status="pending_review",
        score=None,
        summary="该候选人未完成自动审查，需人工处理。",
        risks=[reason],
    )


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
