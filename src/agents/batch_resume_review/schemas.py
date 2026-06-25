from __future__ import annotations

from dataclasses import dataclass, field
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class ResumeElement:
    index: int
    kind: str
    text: str
    source: str = ""
    style: str = ""


@dataclass(frozen=True)
class ResumeChunk:
    chunk_id: str
    title: str
    text: str
    start_element: int
    end_element: int
    char_count: int


@dataclass
class CandidateResume:
    candidate_id: str
    filename: str
    path: str
    candidate_name: str = ""
    elements: list[ResumeElement] = field(default_factory=list)
    chunks: list[ResumeChunk] = field(default_factory=list)
    load_error: str = ""


@dataclass(frozen=True)
class CandidateDecision:
    candidate_id: str
    filename: str
    candidate_name: str
    status: str
    score: int | None
    summary: str
    hard_requirements: list[dict[str, str]] = field(default_factory=list)
    exclusion_reasons: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    interview_questions: list[str] = field(default_factory=list)
    rank: int | None = None


class BatchResumeReviewState(TypedDict):
    resume_paths: list[str]
    job_description_path: NotRequired[str]
    job_description_text: NotRequired[str]
    review_guide_path: NotRequired[str]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    job_description: NotRequired[str]
    review_guide: NotRequired[str]
    university_reference: NotRequired[str]
    candidates: NotRequired[list[CandidateResume]]
    chunk_findings: NotRequired[dict[str, list[str]]]
    decisions: NotRequired[list[CandidateDecision]]
    ranked_candidates: NotRequired[list[CandidateDecision]]
    excluded_candidates: NotRequired[list[CandidateDecision]]
    pending_candidates: NotRequired[list[CandidateDecision]]
    final_report: NotRequired[str]
