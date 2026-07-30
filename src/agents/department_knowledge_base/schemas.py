from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Callable

from pydantic import BaseModel, Field


class Intent(StrEnum):
    SAVE = "save"
    QUERY = "query"
    LIST = "list"
    HELP = "help"
    UNKNOWN = "unknown"


class IntentDecision(BaseModel):
    intent: Intent
    confidence: float = Field(default=0, ge=0, le=1)


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    message: str


ProgressCallback = Callable[[ProgressEvent], None]


class SavedDocument(BaseModel):
    filename: str
    sha256: str
    size_bytes: int
    unchanged: bool = False
    object_bucket: str | None = None
    object_key: str | None = None


class AgentResult(BaseModel):
    intent: Intent
    content: str
    knowledge_id: str
    department: str
    saved_documents: list[SavedDocument] = Field(default_factory=list)
