from __future__ import annotations

from dataclasses import dataclass, field
from typing import NotRequired, TypedDict


SCORE_DIMENSION_SPECS: tuple[tuple[str, str, int], ...] = (
    ("education_major_foundation", "学历、院校、专业与基础知识", 20),
    ("relevant_experience", "相关工作或实习经验", 25),
    ("project_achievement", "项目与成果质量", 25),
    ("skills_tools", "技能与工具匹配", 15),
    ("evidence_credibility", "证据质量与可信度", 10),
    ("collaboration_documentation", "沟通协作与文档", 5),
)


@dataclass(frozen=True)
class ScoreDimension:
    """A user-facing, evidence-backed score rather than hidden model reasoning."""

    id: str
    label: str
    score: int | None
    max_score: int
    evidence: list[str] = field(default_factory=list)
    rationale: str = ""
    deductions: list[str] = field(default_factory=list)


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
    score_breakdown: list[ScoreDimension] = field(default_factory=list)
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
    final_html_report: NotRequired[str]
