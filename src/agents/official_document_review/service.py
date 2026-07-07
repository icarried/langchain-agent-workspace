from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .graph import build_graph
from .llm import MODEL_CONFIGS, create_chat_model

DEFAULT_REVIEW_GUIDE_PATH = Path(__file__).with_name("review_guide") / "党政机关公文格式检查要点.md"


def resolve_workspace_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return _workspace_root() / p


def review_official_document(
    document_path: str | Path,
    *,
    document_type: str = "",
    review_guide_path: str | Path | None = None,
    output_path: str | Path | None = None,
    provider: str = "deepseek",
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_document = resolve_workspace_path(document_path)
    resolved_review_guide = _resolve_optional(review_guide_path) or DEFAULT_REVIEW_GUIDE_PATH
    resolved_output = _resolve_optional(output_path)

    llm = None if dry_run else create_chat_model(provider=provider, model=model)
    graph = build_graph(llm=llm)
    state = graph.invoke(
        {
            "document_path": str(resolved_document),
            "document_type": document_type,
            "review_guide_path": str(resolved_review_guide),
            "output_path": str(resolved_output) if resolved_output else "",
            "provider": provider,
            "model": model or "",
            "dry_run": dry_run,
        }
    )
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    findings = state.get("findings", [])
    return {
        "report": state["final_report"],
        "output_path": str(resolved_output) if resolved_output else "",
        "document_path": str(resolved_document),
        "document_type": document_type,
        "provider": provider,
        "model": model or config.model,
        "dry_run": dry_run,
        "finding_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def _resolve_optional(path: str | Path | None) -> Path | None:
    if path is None or str(path) == "":
        return None
    return resolve_workspace_path(path)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]

