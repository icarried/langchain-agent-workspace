from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

from docx import Document
from langgraph.graph import END, START, StateGraph

from .fonts import inspect_required_fonts
from .formatter import format_docx
from .schemas import (
    DOCX_MIME_TYPE,
    FormattedDocumentResult,
    FormattingState,
)

DEFAULT_MAX_BYTES = 20 * 1024 * 1024


def formatting_max_bytes() -> int:
    value = os.getenv("OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES", "").strip()
    if not value:
        return DEFAULT_MAX_BYTES
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES must be an integer") from exc
    if parsed <= 0:
        raise ValueError("OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES must be positive")
    return parsed


def _output_filename(original_filename: str) -> str:
    safe_name = Path(original_filename).name
    if not safe_name.lower().endswith(".docx"):
        raise ValueError("公文格式化仅支持 DOCX 文件")
    return f"{Path(safe_name).stem}-公文格式化.docx"


def _validate_input(state: FormattingState) -> dict[str, object]:
    source = Path(state["source_path"])
    if source.suffix.lower() != ".docx":
        raise ValueError("公文格式化仅支持 DOCX 文件")
    if not source.is_file():
        raise FileNotFoundError(f"公文文件不存在: {source}")
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("公文 DOCX 为空")
    if size > formatting_max_bytes():
        raise ValueError("公文 DOCX 超过允许大小")
    try:
        Document(source)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError("公文文件不是有效 DOCX") from exc
    return {
        "source_size": size,
        "output_filename": _output_filename(state["original_filename"]),
    }


def _inspect_fonts(_state: FormattingState) -> dict[str, object]:
    return {"font_inspection": inspect_required_fonts()}


def _format_document(state: FormattingState) -> dict[str, object]:
    if state["dry_run"]:
        return {}
    output = Path(state["output_path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    format_docx(state["source_path"], output)
    return {}


def _build_result(state: FormattingState) -> dict[str, object]:
    inspection = state["font_inspection"]
    if state["dry_run"]:
        content = b""
        digest = ""
        size = 0
        report = "公文格式化 dry-run 已完成：输入 DOCX 有效，未生成输出文件。"
    else:
        output = Path(state["output_path"])
        try:
            Document(output)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise ValueError("格式化输出不是有效 DOCX") from exc
        content = output.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        size = len(content)
        report = "公文格式化完成，已按公司验证规则生成新的 DOCX 文件。"
    if inspection.missing:
        report += " 服务端字体检查提示缺少：" + "、".join(inspection.missing) + "。"
    result = FormattedDocumentResult(
        filename=state["output_filename"],
        mime_type=DOCX_MIME_TYPE,
        content=content,
        sha256=digest,
        size=size,
        dry_run=state["dry_run"],
        report=report,
        font_inspection=inspection,
        output_path=state["output_path"] if state.get("persist_output") else "",
    )
    return {"result": result}


def build_graph():
    graph = StateGraph(FormattingState)
    graph.add_node("validate_input", _validate_input)
    graph.add_node("inspect_fonts", _inspect_fonts)
    graph.add_node("format_document", _format_document)
    graph.add_node("build_result", _build_result)
    graph.add_edge(START, "validate_input")
    graph.add_edge("validate_input", "inspect_fonts")
    graph.add_edge("inspect_fonts", "format_document")
    graph.add_edge("format_document", "build_result")
    graph.add_edge("build_result", END)
    return graph.compile()

