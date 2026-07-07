from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class DocumentElement:
    index: int
    kind: str
    text: str
    source: str = ""
    style: str = ""


@dataclass(frozen=True)
class FormatFinding:
    check_id: str
    severity: str
    category: str
    message: str
    suggestion: str
    evidence: str = ""


class OfficialDocumentReviewState(TypedDict):
    document_path: str
    document_type: NotRequired[str]
    review_guide_path: NotRequired[str]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    elements: NotRequired[list[DocumentElement]]
    findings: NotRequired[list[FormatFinding]]
    review_guide: NotRequired[str]
    final_report: NotRequired[str]

