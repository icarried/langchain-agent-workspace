from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

try:
    from langchain_core.documents import Document
except ModuleNotFoundError:
    @dataclass(slots=True)
    class Document:
        page_content: str
        metadata: dict[str, Any]

from kb_api.settings import Settings, get_settings


@dataclass(slots=True)
class RetrievedChunk:
    document: Document
    score: float | None = None


class SupportsSimilaritySearchWithRelevanceScores(Protocol):
    def similarity_search_with_relevance_scores(
        self,
        query: str,
        *,
        k: int,
    ) -> list[tuple[Document, float]]: ...


class RagRetriever:
    def __init__(
        self,
        vectorstore: SupportsSimilaritySearchWithRelevanceScores,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._vectorstore = vectorstore
        self._settings = settings or get_settings()

    def retrieve(self, question: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = top_k or self._settings.top_k
        results = self._vectorstore.similarity_search_with_relevance_scores(question, k=limit)
        return [
            RetrievedChunk(document=document, score=self._normalize_score(score))
            for document, score in results
        ]

    @property
    def min_relevance_score(self) -> float:
        return self._settings.min_relevance_score

    @staticmethod
    def _normalize_score(score: Any) -> float | None:
        if score is None:
            return None
        return max(0.0, min(1.0, float(score)))
