from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    chunk_id: str
    chunk_index: int
    text: str = Field(max_length=1000)
    score: float | None = Field(default=None, ge=0, le=1)


class KnowledgeAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False


class IngestResult(BaseModel):
    knowledge_base: str
    documents_seen: int
    documents_loaded: int
    chunks_written: int
    unchanged: bool = False


class RetrievalResult(BaseModel):
    query: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False


class MultiQueryRetrievalResult(BaseModel):
    queries: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False


class KnowledgeBaseInfo(BaseModel):
    name: str
    namespace: str
    documents_dir: str
    ingested_at: str | None = None
    document_count: int = 0
