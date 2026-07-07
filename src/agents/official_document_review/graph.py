from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .document_loader import load_document_elements
from .format_checks import inspect_official_document
from .llm import MODEL_CONFIGS
from .prompts import REPORT_HUMAN, REPORT_SYSTEM
from .schemas import DocumentElement, FormatFinding, OfficialDocumentReviewState


def build_graph(llm: Any | None = None):
    graph = StateGraph(OfficialDocumentReviewState)
    graph.add_node("load_inputs", _load_inputs)
    graph.add_node("inspect_format", _inspect_format)
    graph.add_node("compose_report", _compose_report(llm))
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "inspect_format")
    graph.add_edge("inspect_format", "compose_report")
    graph.add_edge("compose_report", END)
    return graph.compile()


def _load_inputs(state: OfficialDocumentReviewState) -> OfficialDocumentReviewState:
    return {
        **state,
        "elements": load_document_elements(state["document_path"]),
        "review_guide": _read_optional(state.get("review_guide_path")),
        "document_type": state.get("document_type") or "未说明",
    }


def _inspect_format(state: OfficialDocumentReviewState) -> OfficialDocumentReviewState:
    findings = inspect_official_document(state["document_path"], state.get("elements", []))
    return {**state, "findings": findings}


def _compose_report(llm: Any | None):
    def node(state: OfficialDocumentReviewState) -> OfficialDocumentReviewState:
        elements = state.get("elements", [])
        findings = state.get("findings", [])
        if state.get("dry_run", False) or llm is None:
            report = _dry_run_report(state, elements, findings)
        else:
            prompt = ChatPromptTemplate.from_messages([("system", REPORT_SYSTEM), ("human", REPORT_HUMAN)])
            chain = prompt | llm | StrOutputParser()
            report = chain.invoke(
                {
                    "document_type": state.get("document_type", "未说明"),
                    "review_guide": state.get("review_guide", ""),
                    "element_summary": _element_summary(elements),
                    "findings": _findings_markdown(findings),
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


def _dry_run_report(
    state: OfficialDocumentReviewState,
    elements: list[DocumentElement],
    findings: list[FormatFinding],
) -> str:
    provider = state.get("provider", "deepseek")
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    return (
        "# 公文格式检查 dry-run 报告\n\n"
        "## 工作流可行性\n\n"
        "- 来源经验: FastGPT 公文优化工作流的文件检测和检测结果美化输出。\n"
        "- 支持输入: DOCX、文本型 PDF、TXT、MD；扫描件 OCR 不在第一版范围内。\n"
        f"- 公文类型: {state.get('document_type', '未说明')}\n"
        f"- 模型配置: {config.provider}/{state.get('model') or config.model}。\n"
        f"- 说明: {config.notes}\n\n"
        "## 文本摘要\n\n"
        f"{_element_summary(elements)}\n\n"
        "## 确定性检测结果\n\n"
        f"{_findings_markdown(findings)}\n\n"
        "## 输出边界\n\n"
        "- 当前检查结果用于辅助经办人修改格式，不替代单位公文审核流程。\n"
        "- 非 DOCX 输入无法读取页边距、纸张、字体等版式元数据。\n"
    )


def _element_summary(elements: list[DocumentElement]) -> str:
    lines = ["| 元素 | 类型 | 内容 |", "| --- | --- | --- |"]
    for element in elements[:12]:
        text = element.text.replace("|", "/")
        if len(text) > 80:
            text = f"{text[:80]}..."
        lines.append(f"| {element.index} | {element.kind} | {text} |")
    if len(elements) > 12:
        lines.append(f"| ... | ... | 其余 {len(elements) - 12} 个元素略 |")
    return "\n".join(lines)


def _findings_markdown(findings: list[FormatFinding]) -> str:
    if not findings:
        return "- 未发现问题。"
    lines = ["| 严重度 | 类别 | 问题 | 建议 | 证据 |", "| --- | --- | --- | --- | --- |"]
    for finding in findings:
        lines.append(
            "| "
            f"{finding.severity} | {finding.category} | {finding.message} | "
            f"{finding.suggestion} | {finding.evidence or '-'} |"
        )
    return "\n".join(lines)

