from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from .chunking import chunk_elements
from .docx_loader import load_docx_elements
from .llm import MODEL_CONFIGS
from .prompts import AGGREGATE_HUMAN, AGGREGATE_SYSTEM, CHUNK_REVIEW_HUMAN, CHUNK_REVIEW_SYSTEM
from .schemas import DocumentChunk, TenderReviewState


def build_graph(llm: Any | None = None):
    graph = StateGraph(TenderReviewState)
    graph.add_node("load_inputs", _load_inputs)
    graph.add_node("split_document", _split_document)
    graph.add_node("review_chunks", _review_chunks(llm))
    graph.add_node("aggregate_report", _aggregate_report(llm))
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "split_document")
    graph.add_edge("split_document", "review_chunks")
    graph.add_edge("review_chunks", "aggregate_report")
    graph.add_edge("aggregate_report", END)
    return graph.compile()


def _load_inputs(state: TenderReviewState) -> TenderReviewState:
    elements = load_docx_elements(state["docx_path"])
    return {
        **state,
        "elements": elements,
        "review_guide": _read_optional(state.get("review_guide_path")),
        "reference_catalog": _read_optional(state.get("catalog_path")),
    }


def _split_document(state: TenderReviewState) -> TenderReviewState:
    provider = state.get("provider", "deepseek")
    max_chars = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"]).practical_chunk_chars
    chunks = chunk_elements(state.get("elements", []), max_chars=max_chars)
    return {**state, "chunks": chunks}


def _review_chunks(llm: Any | None):
    def node(state: TenderReviewState) -> TenderReviewState:
        chunks = state.get("chunks", [])
        if state.get("dry_run", False) or llm is None:
            findings = [_dry_run_finding(chunk) for chunk in chunks]
            return {**state, "chunk_findings": findings}

        prompt = ChatPromptTemplate.from_messages(
            [("system", CHUNK_REVIEW_SYSTEM), ("human", CHUNK_REVIEW_HUMAN)]
        )
        chain = prompt | llm | StrOutputParser()
        findings = []
        for chunk in chunks:
            findings.append(
                chain.invoke(
                    {
                        "review_guide": state.get("review_guide", ""),
                        "reference_catalog": state.get("reference_catalog", ""),
                        "chunk_id": chunk.chunk_id,
                        "title": chunk.title,
                        "start_element": chunk.start_element,
                        "end_element": chunk.end_element,
                        "chunk_text": chunk.text,
                    }
                )
            )
        return {**state, "chunk_findings": findings}

    return node


def _aggregate_report(llm: Any | None):
    def node(state: TenderReviewState) -> TenderReviewState:
        chunks = state.get("chunks", [])
        findings = state.get("chunk_findings", [])
        chunk_summary = _chunk_summary(chunks)
        if state.get("dry_run", False) or llm is None:
            report = _dry_run_report(state, chunk_summary, findings)
        else:
            prompt = ChatPromptTemplate.from_messages(
                [("system", AGGREGATE_SYSTEM), ("human", AGGREGATE_HUMAN)]
            )
            chain = prompt | llm | StrOutputParser()
            report = chain.invoke(
                {
                    "chunk_summary": chunk_summary,
                    "chunk_findings": "\n\n".join(findings),
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


def _chunk_summary(chunks: list[DocumentChunk]) -> str:
    lines = ["| 片段 | 标题 | 元素范围 | 字符数 |", "| --- | --- | --- | ---: |"]
    for chunk in chunks:
        lines.append(
            f"| {chunk.chunk_id} | {chunk.title} | {chunk.start_element}-{chunk.end_element} | {chunk.char_count} |"
        )
    return "\n".join(lines)


def _dry_run_finding(chunk: DocumentChunk) -> str:
    return (
        f"## {chunk.chunk_id} {chunk.title}\n"
        f"- dry-run: 已生成审查片段，元素范围 {chunk.start_element}-{chunk.end_element}，"
        f"字符数 {chunk.char_count}。实际问题识别需要接入模型运行。"
    )


def _dry_run_report(
    state: TenderReviewState,
    chunk_summary: str,
    findings: list[str],
) -> str:
    provider = state.get("provider", "deepseek")
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    return (
        "# 招标文件格式审查 dry-run 报告\n\n"
        "## 工作流可行性\n\n"
        "- 模型配置: 由服务端环境统一管理。\n"
        f"- 实用分块上限: 每块约 {config.practical_chunk_chars} 字符。\n"
        f"- 说明: {config.notes}\n"
        "- 对 10 万字以上招标文件，不建议整篇一次审查；即使模型上下文足够，"
        "分块审查 + 汇总复核更利于证据定位、跨章节一致性追踪和失败重试。\n\n"
        "## 分块概况\n\n"
        f"{chunk_summary}\n\n"
        "## dry-run 节点输出\n\n"
        f"{chr(10).join(findings)}\n"
    )
