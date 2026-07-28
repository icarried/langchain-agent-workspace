from __future__ import annotations

from enum import StrEnum

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
