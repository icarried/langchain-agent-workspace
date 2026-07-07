from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .graph import build_graph
from .llm import MODEL_CONFIGS, create_chat_model


def resolve_workspace_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return _workspace_root() / p


def screen_resumes(
    resume_paths: list[str | Path],
    *,
    job_description_path: str | Path | None = None,
    job_description_text: str | None = None,
    position_name: str = "",
    department: str = "",
    level_range: str = "",
    hard_conditions: list[str] | None = None,
    bonus_conditions: list[str] | None = None,
    reject_conditions: list[str] | None = None,
    output_path: str | Path | None = None,
    provider: str = "deepseek",
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_resumes = [resolve_workspace_path(path) for path in resume_paths]
    resolved_jd = _resolve_optional(job_description_path)
    resolved_output = _resolve_optional(output_path)
    llm = None if dry_run else create_chat_model(provider=provider, model=model)
    graph = build_graph(llm=llm)
    state = graph.invoke(
        {
            "resume_paths": [str(path) for path in resolved_resumes],
            "job_description_path": str(resolved_jd) if resolved_jd else "",
            "job_description_text": job_description_text or "",
            "position_name": position_name,
            "department": department,
            "level_range": level_range,
            "hard_conditions": hard_conditions or [],
            "bonus_conditions": bonus_conditions or [],
            "reject_conditions": reject_conditions or [],
            "output_path": str(resolved_output) if resolved_output else "",
            "provider": provider,
            "model": model or "",
            "dry_run": dry_run,
        }
    )
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    return {
        "report": state["final_report"],
        "output_path": str(resolved_output) if resolved_output else "",
        "resume_paths": [str(path) for path in resolved_resumes],
        "provider": provider,
        "model": model or config.model,
        "dry_run": dry_run,
        "candidate_count": len(state.get("scores", [])),
        "scores": [asdict(score) for score in state.get("scores", [])],
        "criteria": asdict(state["criteria"]),
    }


def _resolve_optional(path: str | Path | None) -> Path | None:
    if path is None or str(path) == "":
        return None
    return resolve_workspace_path(path)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]

