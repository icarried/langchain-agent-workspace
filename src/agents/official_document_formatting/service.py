from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .graph import build_graph


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

    if output_path:
        target = resolve_workspace_path(output_path)
        result = _invoke_graph(
            source,
            target,
            source_name,
            dry_run=dry_run,
            persist_output=True,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="official-document-formatting-") as temporary:
            target = Path(temporary) / "formatted.docx"
            result = _invoke_graph(
                source,
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
