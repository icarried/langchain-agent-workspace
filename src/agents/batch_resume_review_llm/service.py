from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv

from .graph import build_graph
from .llm import MODEL_CONFIGS, create_chat_model
from .resume_loader import is_remote_resume_source, safe_resume_source_label

DEFAULT_REVIEW_GUIDE_PATH = Path(__file__).with_name("review_guide") / "批量简历审查与排序规则.md"
MAX_RESUMES = 100


def resolve_workspace_path(path: str | Path) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return Path.cwd() / p


def review_resumes(
    resume_paths: Sequence[str | Path],
    *,
    job_description_path: str | Path | None = None,
    job_description_text: str | None = None,
    review_guide_path: str | Path | None = None,
    output_path: str | Path | None = None,
    provider: str = "deepseek",
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    load_dotenv(Path.cwd() / ".env.local")
    sources = [_resolve_resume_source(path) for path in resume_paths]
    if not sources:
        raise ValueError("at least one resume is required")
    if len(sources) > MAX_RESUMES:
        raise ValueError(f"a batch can contain at most {MAX_RESUMES} resumes")
    normalized = [_normalize_resume_source(source) for source in sources]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate resume paths are not allowed")
    if not (job_description_text or "").strip() and not job_description_path:
        raise ValueError("job description is required for batch screening and ranking")

    resolved_jd = _resolve_optional(job_description_path)
    resolved_guide = _resolve_optional(review_guide_path) or DEFAULT_REVIEW_GUIDE_PATH
    resolved_output = _resolve_optional(output_path)
    llm = None if dry_run else create_chat_model(provider=provider, model=model)
    state = build_graph(llm=llm).invoke(
        {
            "resume_paths": [str(source) for source in sources],
            "job_description_path": str(resolved_jd) if resolved_jd else "",
            "job_description_text": job_description_text or "",
            "review_guide_path": str(resolved_guide),
            "output_path": str(resolved_output) if resolved_output else "",
            "provider": provider,
            "model": model or "",
            "dry_run": dry_run,
        }
    )
    config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    candidates = state.get("candidates", [])
    ranked = state.get("ranked_candidates", [])
    excluded = state.get("excluded_candidates", [])
    pending = state.get("pending_candidates", [])
    decisions = state.get("decisions", [])
    return {
        "report": state["final_report"],
        "report_html": state["final_html_report"],
        "output_path": str(resolved_output) if resolved_output else "",
        "resume_paths": [safe_resume_source_label(source) for source in sources],
        "provider": provider,
        "model": model or config.model,
        "dry_run": dry_run,
        "candidate_count": len(candidates),
        "chunk_count": sum(len(candidate.chunks) for candidate in candidates),
        "qualified_count": len(ranked),
        "excluded_count": len(excluded),
        "pending_count": len(pending),
        "ranking": [asdict(item) for item in ranked],
        "excluded": [asdict(item) for item in excluded],
        "pending": [asdict(item) for item in pending],
        "candidates": [asdict(item) for item in decisions],
    }


def _resolve_optional(path: str | Path | None) -> Path | None:
    if path is None or str(path) == "":
        return None
    return resolve_workspace_path(path)


def _resolve_resume_source(source: str | Path) -> str | Path:
    if is_remote_resume_source(source):
        return str(source)
    return resolve_workspace_path(source)


def _normalize_resume_source(source: str | Path) -> str:
    if is_remote_resume_source(source):
        return str(source)
    return str(Path(source).resolve()).lower()
