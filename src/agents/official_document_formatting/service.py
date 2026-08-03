from __future__ import annotations

import tempfile
from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from src.document_conversion import convert_doc_to_docx

from .graph import build_graph, formatting_max_bytes


def resolve_workspace_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return _workspace_root() / candidate


def format_official_document(
    source_path: str | Path,
    *,
    output_path: str | Path | None = None,
    original_filename: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    source = resolve_workspace_path(source_path)
    source_name = Path(original_filename or source.name).name
    persistent_output = bool(output_path)

    with _materialize_formatting_source(source) as formatting_source:
        if output_path:
            target = resolve_workspace_path(output_path)
            result = _invoke_graph(
                formatting_source,
                target,
                source_name,
                dry_run=dry_run,
                persist_output=True,
            )
        else:
            with tempfile.TemporaryDirectory(
                prefix="official-document-formatting-"
            ) as temporary:
                target = Path(temporary) / "formatted.docx"
                result = _invoke_graph(
                    formatting_source,
                    target,
                    source_name,
                    dry_run=dry_run,
                    persist_output=False,
                )

    return {
        "filename": result.filename,
        "mime_type": result.mime_type,
        "content": result.content,
        "sha256": result.sha256,
        "size": result.size,
        "dry_run": result.dry_run,
        "report": result.report,
        "findings": [asdict(finding) for finding in result.findings],
        "output_path": str(resolve_workspace_path(output_path)) if persistent_output else "",
    }


def _invoke_graph(
    source: Path,
    output: Path,
    original_filename: str,
    *,
    dry_run: bool,
    persist_output: bool,
):
    state = build_graph().invoke(
        {
            "source_path": str(source),
            "output_path": str(output),
            "original_filename": original_filename,
            "dry_run": dry_run,
            "persist_output": persist_output,
        }
    )
    return state["result"]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


@contextmanager
def _materialize_formatting_source(source: Path) -> Iterator[Path]:
    """Yield a valid DOCX source, converting a legacy DOC only for this request."""
    suffix = source.suffix.lower()
    if suffix == ".docx":
        yield source
        return
    if suffix != ".doc":
        raise ValueError("公文格式化仅支持 DOCX 或 DOC 文件")
    if not source.is_file():
        raise FileNotFoundError(f"公文文件不存在: {source}")
    source_size = source.stat().st_size
    if source_size <= 0:
        raise ValueError("公文 DOC 为空")
    if source_size > formatting_max_bytes():
        raise ValueError("公文 DOC 超过允许大小")

    converted = convert_doc_to_docx(source.read_bytes(), source=source.name)
    with tempfile.TemporaryDirectory(prefix="official-document-formatting-doc-") as temporary:
        converted_path = Path(temporary) / f"{source.stem}.docx"
        converted_path.write_bytes(converted)
        yield converted_path
