from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .chunking import chunk_elements
from .contract_loader import load_contract_elements
from .llm import MODEL_CONFIGS
from .prompts import AGGREGATE_HUMAN, AGGREGATE_SYSTEM, DIMENSION_REVIEW_HUMAN, DIMENSION_REVIEW_SYSTEM
from .schemas import ContractChunk, ContractReviewState


REVIEW_DIMENSIONS = [
    ("主体合法性审查", "核查签约主体资格、授权权限、分支机构签约资格、特殊资质和资信线索。"),
    ("内容合法性审查", "识别强制性规定冲突、标的合法性、审批登记招投标程序和无效条款风险。"),
    ("条款完备性与明确性审查", "检查主体、标的、数量质量、价款、履行、违约责任、争议解决等核心条款。"),
    ("风险防控与实用性审查", "关注违约责任可计算性、争议解决可执行性、保密知识产权、变更和不可抗力机制。"),
    ("形式与表述规范审查", "审查结构顺序、编号引用、定义一致性、模糊表述、签署盖章和附件衔接。"),
    ("履行与终止审查", "核验履约监督、验收付款、通知义务、解除权、终止后返还结算和后合同义务。"),
]


def build_graph(llm: Any | None = None):
    graph = StateGraph(ContractReviewState)
    graph.add_node("load_inputs", _load_inputs)
    graph.add_node("split_contract", _split_contract)
    graph.add_node("review_dimensions", _review_dimensions(llm))
    graph.add_node("score_and_aggregate", _score_and_aggregate(llm))
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "split_contract")
    graph.add_edge("split_contract", "review_dimensions")
    graph.add_edge("review_dimensions", "score_and_aggregate")
    graph.add_edge("score_and_aggregate", END)
    return graph.compile()


def _load_inputs(state: ContractReviewState) -> ContractReviewState:
    return {
        **state,
        "elements": load_contract_elements(state["contract_path"]),
        "review_guide": _read_optional(state.get("review_guide_path")),
        "client_role": state.get("client_role") or "未说明",
        "contract_type": state.get("contract_type") or "未说明",
        "transaction_background": state.get("transaction_background") or "未说明",
    }


def _split_contract(state: ContractReviewState) -> ContractReviewState:
    provider = state.get("provider", "deepseek")
    max_chars = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"]).practical_chunk_chars
    chunks = chunk_elements(state.get("elements", []), max_chars=max_chars)
    return {**state, "chunks": chunks}


def _review_dimensions(llm: Any | None):
    def node(state: ContractReviewState) -> ContractReviewState:
        chunks = state.get("chunks", [])
        if state.get("dry_run", False) or llm is None:
            findings = [_dry_run_finding(chunk) for chunk in chunks]
            return {**state, "dimension_findings": findings}

        prompt = ChatPromptTemplate.from_messages(
            [("system", DIMENSION_REVIEW_SYSTEM), ("human", DIMENSION_REVIEW_HUMAN)]
        )
        chain = prompt | llm | StrOutputParser()
        jobs = []
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(chunks) * len(REVIEW_DIMENSIONS)))) as executor:
            for chunk in chunks:
                for dimension_name, dimension_focus in REVIEW_DIMENSIONS:
                    jobs.append(
                        executor.submit(
                            chain.invoke,
                            {
                                "client_role": state.get("client_role", "未说明"),
                                "contract_type": state.get("contract_type", "未说明"),
                                "transaction_background": state.get("transaction_background", "未说明"),
                                "review_guide": state.get("review_guide", ""),
                                "dimension_name": dimension_name,
                                "dimension_focus": dimension_focus,
                                "chunk_id": chunk.chunk_id,
                                "title": chunk.title,
                                "start_element": chunk.start_element,
                                "end_element": chunk.end_element,
                                "chunk_text": chunk.text,
                            },
                        )
                    )
            findings = [future.result() for future in as_completed(jobs)]
        return {**state, "dimension_findings": findings}

    return node


def _score_and_aggregate(llm: Any | None):
    def node(state: ContractReviewState) -> ContractReviewState:
        chunks = state.get("chunks", [])
        findings = state.get("dimension_findings", [])
        chunk_summary = _chunk_summary(chunks)
        if state.get("dry_run", False) or llm is None:
            report = _dry_run_report(state, chunk_summary, findings)
        else:
            prompt = ChatPromptTemplate.from_messages([("system", AGGREGATE_SYSTEM), ("human", AGGREGATE_HUMAN)])
            chain = prompt | llm | StrOutputParser()
            report = chain.invoke(
                {
                    "client_role": state.get("client_role", "未说明"),
                    "contract_type": state.get("contract_type", "未说明"),
                    "transaction_background": state.get("transaction_background", "未说明"),
                    "chunk_summary": chunk_summary,
                    "dimension_findings": "\n\n".join(findings),
                }
            )

        output_path = state.get("output_path")
        if output_path:
            Path(output_path).write_text(report, encoding="utf-8")
        return {**state, "final_report": report}

    return node


def _read_optional(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"reference file not found: {p}")
    parts = [f"# 审查规则文件: {p.name}\n\n{p.read_text(encoding='utf-8')}"]
    if p.is_file() and p.parent.name == "review_guide":
        for sibling in sorted(p.parent.glob("*.md")):
            if sibling == p:
                continue
            parts.append(f"# 补充审查依据: {sibling.name}\n\n{sibling.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(parts)


def _chunk_summary(chunks: list[ContractChunk]) -> str:
    lines = ["| 片段 | 标题 | 元素范围 | 字符数 |", "| --- | --- | --- | ---: |"]
    for chunk in chunks:
        lines.append(
            f"| {chunk.chunk_id} | {chunk.title} | {chunk.start_element}-{chunk.end_element} | {chunk.char_count} |"
        )
    return "\n".join(lines)


def _dry_run_finding(chunk: ContractChunk) -> str:
    dimensions = "\n".join(f"- {name}: {focus}" for name, focus in REVIEW_DIMENSIONS)
    return (
        f"## {chunk.chunk_id} {chunk.title}\n"
        f"- dry-run: 已生成合同审查片段，元素范围 {chunk.start_element}-{chunk.end_element}，"
        f"字符数 {chunk.char_count}。\n"
        "- 正式运行将并行检查六个维度:\n"
        f"{dimensions}"
    )


def _dry_run_report(state: ContractReviewState, chunk_summary: str, findings: list[str]) -> str:
    provider = state.get("provider", "deepseek")
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    return (
        "# 合同审查 dry-run 报告\n\n"
        "## 工作流可行性\n\n"
        "- 来源经验: FastGPT 合同审查大师工作流的表单输入、六维并行审查、评分评级和综合整改建议。\n"
        "- 支持输入: DOCX、文本型 PDF、TXT、MD；扫描件 OCR 不在第一版范围内。\n"
        f"- 委托方角色: {state.get('client_role', '未说明')}\n"
        f"- 合同类型: {state.get('contract_type', '未说明')}\n"
        f"- 交易背景: {state.get('transaction_background', '未说明')}\n"
        f"- 模型配置: {config.provider}/{state.get('model') or config.model}。\n"
        f"- 实用分块上限: 每块约 {config.practical_chunk_chars} 字符。\n"
        f"- 说明: {config.notes}\n\n"
        "## 分块概况\n\n"
        f"{chunk_summary}\n\n"
        "## 审查结构\n\n"
        "- 六个维度: 主体合法性、内容合法性、条款完备性与明确性、风险防控与实用性、形式与表述规范、履行与终止。\n"
        "- 评分评级: 法律合规性 35%、风险控制 40%、条款清晰度 25%，输出 A/B/C/D 签署建议。\n"
        "- 输出边界: 标记证据编号和待补充资料，不替代执业律师正式法律意见。\n\n"
        "## dry-run 节点输出\n\n"
        f"{chr(10).join(findings)}\n"
    )

