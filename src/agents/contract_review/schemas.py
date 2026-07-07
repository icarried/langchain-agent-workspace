from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass(frozen=True)
class ContractElement:
    index: int
    kind: str
    text: str
    source: str = ""
    style: str = ""


@dataclass(frozen=True)
class ContractChunk:
    chunk_id: str
    title: str
    text: str
    start_element: int
    end_element: int
    char_count: int


class ContractReviewState(TypedDict):
    contract_path: str
    client_role: NotRequired[str]
    contract_type: NotRequired[str]
    transaction_background: NotRequired[str]
    review_guide_path: NotRequired[str]
    output_path: NotRequired[str]
    dry_run: NotRequired[bool]
    provider: NotRequired[str]
    model: NotRequired[str]
    elements: NotRequired[list[ContractElement]]
    chunks: NotRequired[list[ContractChunk]]
    review_guide: NotRequired[str]
    dimension_findings: NotRequired[list[str]]
    final_report: NotRequired[str]

