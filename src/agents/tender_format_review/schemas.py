from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class DocumentElement:
    index: int
    kind: str
    text: str
    style: str = ""


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    title: str
    text: str
    start_element: int
    end_element: int
    char_count: int


class TenderReviewState(TypedDict):
    docx_path: str
    review_guide_path: NotRequired[str]
    catalog_path: NotRequired[str]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    elements: NotRequired[list[DocumentElement]]
    chunks: NotRequired[list[DocumentChunk]]
    review_guide: NotRequired[str]
    reference_catalog: NotRequired[str]
    chunk_findings: NotRequired[list[str]]
    final_report: NotRequired[str]
