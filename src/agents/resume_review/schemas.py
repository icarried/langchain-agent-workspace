from __future__ import annotations

from dataclasses import dataclass
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


class ResumeReviewState(TypedDict):
    resume_path: str
    job_description_path: NotRequired[str]
    job_description_text: NotRequired[str]
    review_guide_path: NotRequired[str]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    elements: NotRequired[list[ResumeElement]]
    chunks: NotRequired[list[ResumeChunk]]
    review_guide: NotRequired[str]
    university_reference: NotRequired[str]
    job_description: NotRequired[str]
    chunk_findings: NotRequired[list[str]]
    final_report: NotRequired[str]
