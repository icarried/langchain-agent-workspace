from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    ok = "ok"
    degraded = "degraded"
    missing_config = "missing_config"


class ComponentHealth(BaseModel):
    status: HealthStatus
    detail: str | None = None


class HealthResponse(BaseModel):
    api: ComponentHealth
    chroma: ComponentHealth
    model: ComponentHealth


class Citation(BaseModel):
    source: str
    chunk_id: str
    chunk_index: int
    text: str = Field(default="", max_length=1000)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    docs_dir: str | None = None
    knowledge_base: str | None = None


class IngestResponse(BaseModel):
    documents_seen: int
    documents_loaded: int
    chunks_written: int
    collection: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False


class ChatCompletionMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionsRequest(BaseModel):
    model: str = "langchain-knowledge-base-agent"
    messages: list[ChatCompletionMessage] = Field(default_factory=list)
    stream: bool = False
    top_k: int | None = Field(default=None, ge=1, le=20)
    knowledge_base: str | None = None


class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    knowledge_base: str | None = None


class RetrievalResponse(BaseModel):
    query: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False


class KnowledgeBaseInfo(BaseModel):
    name: str
    description: str
    docs_dir: str
    collection: str
    keywords: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    selected_knowledge_base: str
    reason: str
    candidates: list[KnowledgeBaseInfo] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
