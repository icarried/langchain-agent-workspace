from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict

from .compliance import ComplianceFinding

DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@dataclass(frozen=True)
class FormattedDocumentResult:
    filename: str
    mime_type: str
    content: bytes
    sha256: str
    size: int
    dry_run: bool
    report: str
    findings: tuple[ComplianceFinding, ...]
    output_path: str = ""


class FormattingState(TypedDict):
    source_path: str
    output_path: str
    original_filename: str
    dry_run: bool
    persist_output: NotRequired[bool]
    source_size: NotRequired[int]
    output_filename: NotRequired[str]
    result: NotRequired[FormattedDocumentResult]
