from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .criteria import build_criteria
from .llm import MODEL_CONFIGS
from .prompts import REPORT_HUMAN, REPORT_SYSTEM
from .resume_loader import load_candidate
from .schemas import CandidateScore, ScreeningCriteria, SmartResumeScreeningState
from .scoring import score_candidate


def build_graph(llm: Any | None = None):
    graph = StateGraph(SmartResumeScreeningState)
    graph.add_node("load_inputs", _load_inputs)
    graph.add_node("score_candidates", _score_candidates)
    graph.add_node("compose_report", _compose_report(llm))
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "score_candidates")
    graph.add_edge("score_candidates", "compose_report")
    graph.add_edge("compose_report", END)
    return graph.compile()


def _load_inputs(state: SmartResumeScreeningState) -> SmartResumeScreeningState:
    jd = _read_job_description(state)
    criteria = build_criteria(
        job_description=jd,
        position_name=state.get("position_name", ""),
        department=state.get("department", ""),
        level_range=state.get("level_range", ""),
        hard_conditions=state.get("hard_conditions", []),
        bonus_conditions=state.get("bonus_conditions", []),
        reject_conditions=state.get("reject_conditions", []),
    )
    candidates = [load_candidate(path) for path in state.get("resume_paths", [])]
    return {**state, "criteria": criteria, "candidates": candidates}


def _score_candidates(state: SmartResumeScreeningState) -> SmartResumeScreeningState:
    criteria = state["criteria"]
    scores = [score_candidate(candidate, criteria) for candidate in state.get("candidates", [])]
    scores.sort(key=lambda item: (item.status != "qualified", -item.total_score, item.display_name))
    return {**state, "scores": scores}


def _compose_report(llm: Any | None):
    def node(state: SmartResumeScreeningState) -> SmartResumeScreeningState:
        criteria = state["criteria"]
        scores = state.get("scores", [])
        if state.get("dry_run", False) or llm is None:
            report = _dry_run_report(state, criteria, scores)
        else:
            prompt = ChatPromptTemplate.from_messages([("system", REPORT_SYSTEM), ("human", REPORT_HUMAN)])
            chain = prompt | llm | StrOutputParser()
            report = chain.invoke({"criteria": _criteria_markdown(criteria), "scores": _scores_markdown(scores)})
        output_path = state.get("output_path")
        if output_path:
            Path(output_path).write_text(report, encoding="utf-8")
        return {**state, "final_report": report}

    return node


def _read_job_description(state: SmartResumeScreeningState) -> str:
    text = (state.get("job_description_text") or "").strip()
    if text:
        return text
    path = state.get("job_description_path")
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"job description file not found: {p}")
    return p.read_text(encoding="utf-8").strip()


def _dry_run_report(
    state: SmartResumeScreeningState,
    criteria: ScreeningCriteria,
    scores: list[CandidateScore],
) -> str:
    provider = state.get("provider", "deepseek")
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    return (
        "# 智能简历筛选 dry-run 报告\n\n"
        "## 工作流可行性\n\n"
        "- 来源经验: FastGPT 智能简历筛选工作流的岗位参数、硬性条件、加分项、淘汰项、量化评分和排行榜。\n"
        "- 实现方式: 本地解析简历，确定性初筛和打分，正式模式再用模型整理招聘报告。\n"
        f"- 模型配置: {config.provider}/{state.get('model') or config.model}。\n"
        f"- 说明: {config.notes}\n\n"
        "## 岗位筛选配置\n\n"
        f"{_criteria_markdown(criteria)}\n\n"
        "## 候选人排行榜\n\n"
        f"{_scores_markdown(scores)}\n"
    )


def _criteria_markdown(criteria: ScreeningCriteria) -> str:
    return (
        f"- 职位名称: {criteria.position_name}\n"
        f"- 所属部门: {criteria.department}\n"
        f"- 职级范围: {criteria.level_range}\n"
        f"- 硬性条件: {', '.join(criteria.hard_conditions) or '未配置'}\n"
        f"- 优先条件: {', '.join(criteria.bonus_conditions) or '未配置'}\n"
        f"- 淘汰条件: {', '.join(criteria.reject_conditions) or '未配置'}\n"
        "- 权重: 教育背景 20%，工作经验 35%，技术能力 25%，项目成果 15%，软性素质 5%"
    )


def _scores_markdown(scores: list[CandidateScore]) -> str:
    if not scores:
        return "未提供候选人简历。"
    lines = [
        "| 排名 | 姓名 | 状态 | 总分 | 命中硬性条件 | 缺失硬性条件 | 加分项 | 风险提示 | 推荐意见 |",
        "| ---: | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for index, score in enumerate(scores, start=1):
        lines.append(
            f"| {index} | {score.display_name} | {score.status} | {score.total_score} | "
            f"{', '.join(score.matched_hard_conditions) or '-'} | "
            f"{', '.join(score.missing_hard_conditions) or '-'} | "
            f"{', '.join(score.matched_bonus_conditions) or '-'} | "
            f"{', '.join(score.risks) or '-'} | {score.recommendation} |"
        )
    return "\n".join(lines)

