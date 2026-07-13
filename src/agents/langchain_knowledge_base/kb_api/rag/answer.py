from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from kb_api.rag.retriever import RagRetriever, RetrievedChunk
from kb_api.schemas import ChatResponse, Citation
from kb_api.settings import Settings, get_settings

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "rag_answer.md"
REFUSAL_MESSAGE = "I don't have enough evidence in the knowledge base to answer that."


class SupportsInvoke(Protocol):
    def invoke(self, payload: Any) -> Any: ...


def load_rag_prompt(path: Path = PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8").strip()


class RagAnswerService:
    def __init__(
        self,
        *,
        retriever: RagRetriever,
        chat_model: SupportsInvoke,
        settings: Settings | None = None,
        prompt_path: Path = PROMPT_PATH,
    ) -> None:
        self._retriever = retriever
        self._chat_model = chat_model
        self._settings = settings or get_settings()
        self._prompt_path = prompt_path

    def answer(self, question: str, *, top_k: int | None = None) -> ChatResponse:
        chunks = self._retriever.retrieve(question, top_k=top_k)
        if not chunks:
            return self._refusal()

        citations = build_citations(chunks)
        if not citations:
            return self._refusal()

        if not self._has_sufficient_evidence(citations):
            return self._refusal()

        prompt = load_rag_prompt(self._prompt_path)
        context = render_context(citations)
        response = self._chat_model.invoke(
            prompt.format(question=question, context=context)
        )
        answer_text = coerce_model_text(response)
        return ChatResponse(answer=answer_text, citations=citations, refused=False)

    def _has_sufficient_evidence(self, citations: list[Citation]) -> bool:
        threshold = self._settings.min_relevance_score
        return any(citation.score is None or citation.score >= threshold for citation in citations)

    @staticmethod
    def _refusal() -> ChatResponse:
        return ChatResponse(answer=REFUSAL_MESSAGE, citations=[], refused=True)


def build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    for chunk in chunks:
        metadata = dict(chunk.document.metadata)
        chunk_id = _pick_first_str(metadata, "chunk_id", "id")
        source = _pick_first_str(metadata, "source", "path")
        chunk_index = metadata.get("chunk_index")
        if chunk_id is None or source is None or not isinstance(chunk_index, int):
            continue

        payload = {
            "source": source,
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "text": chunk.document.page_content[:1000],
            "score": chunk.score,
            "metadata": metadata,
        }
        try:
            citations.append(Citation.model_validate(payload))
        except ValidationError:
            continue
    return citations


def render_context(citations: list[Citation]) -> str:
    parts = []
    for citation in citations:
        parts.append(
            f"Source: {citation.source}\n"
            f"Chunk ID: {citation.chunk_id}\n"
            f"Chunk Index: {citation.chunk_index}\n"
            f"Score: {citation.score}\n"
            f"Excerpt: {citation.text}"
        )
    return "\n\n".join(parts)


def coerce_model_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()

    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        if text_parts:
            return "\n".join(text_parts).strip()

    return str(response).strip()


def _pick_first_str(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None
