from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class ScreeningCriteria:
    position_name: str
    department: str
    level_range: str
    hard_conditions: tuple[str, ...]
    bonus_conditions: tuple[str, ...]
    reject_conditions: tuple[str, ...]
    education_weight: int
    experience_weight: int
    skill_weight: int
    project_weight: int
    soft_weight: int


@dataclass(frozen=True)
class CandidateProfile:
    filename: str
    display_name: str
    text: str


@dataclass(frozen=True)
class CandidateScore:
    filename: str
    display_name: str
    status: str
    total_score: int
    matched_hard_conditions: tuple[str, ...]
    missing_hard_conditions: tuple[str, ...]
    matched_bonus_conditions: tuple[str, ...]
    reject_hits: tuple[str, ...]
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    recommendation: str


class SmartResumeScreeningState(TypedDict):
    resume_paths: list[str]
    job_description_path: NotRequired[str]
    job_description_text: NotRequired[str]
    position_name: NotRequired[str]
    department: NotRequired[str]
    level_range: NotRequired[str]
    hard_conditions: NotRequired[list[str]]
    bonus_conditions: NotRequired[list[str]]
    reject_conditions: NotRequired[list[str]]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    criteria: NotRequired[ScreeningCriteria]
    candidates: NotRequired[list[CandidateProfile]]
    scores: NotRequired[list[CandidateScore]]
    final_report: NotRequired[str]

