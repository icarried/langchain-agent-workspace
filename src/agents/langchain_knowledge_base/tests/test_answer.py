from pathlib import Path

from kb_api.rag.answer import PROMPT_PATH, REFUSAL_MESSAGE, RagAnswerService
from kb_api.rag.retriever import Document, RetrievedChunk
from kb_api.settings import Settings


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def retrieve(self, question: str, *, top_k: int | None = None):
        self.calls.append((question, top_k))
        return self.chunks


class FakeChatModel:
    def __init__(self, response="stubbed answer"):
        self.response = response
        self.calls = []

    def invoke(self, prompt):
        self.calls.append(prompt)
        return self.response


def make_chunk(*, score: float | None = 0.9, chunk_id: str = "chunk-1", source: str = "guide.md"):
    return RetrievedChunk(
        document=Document(
            page_content="The system supports local document retrieval.",
            metadata={"chunk_id": chunk_id, "chunk_index": 0, "source": source},
        ),
        score=score,
    )


def test_answer_service_loads_prompt_from_markdown_file():
    retriever = FakeRetriever([make_chunk()])
    chat_model = FakeChatModel("Answer from model")
    service = RagAnswerService(
        retriever=retriever,
        chat_model=chat_model,
        settings=Settings(min_relevance_score=0.25),
    )

    response = service.answer("What does the system support?")

    assert response.refused is False
    assert response.answer == "Answer from model"
    assert len(response.citations) == 1
    assert chat_model.calls
    loaded_prompt = Path(PROMPT_PATH).read_text(encoding="utf-8").strip()
    assert loaded_prompt.splitlines()[0] in chat_model.calls[0]
    assert "What does the system support?" in chat_model.calls[0]
    assert "The system supports local document retrieval." in chat_model.calls[0]


def test_answer_service_refuses_when_no_evidence():
    retriever = FakeRetriever([])
    chat_model = FakeChatModel()
    service = RagAnswerService(
        retriever=retriever,
        chat_model=chat_model,
        settings=Settings(min_relevance_score=0.25),
    )

    response = service.answer("Unknown question")

    assert response == response.model_copy(update={"answer": REFUSAL_MESSAGE, "citations": [], "refused": True})
    assert chat_model.calls == []


def test_answer_service_refuses_when_all_scores_below_threshold():
    retriever = FakeRetriever([make_chunk(score=0.2)])
    chat_model = FakeChatModel()
    service = RagAnswerService(
        retriever=retriever,
        chat_model=chat_model,
        settings=Settings(min_relevance_score=0.25),
    )

    response = service.answer("Unknown question")

    assert response.refused is True
    assert response.citations == []
    assert chat_model.calls == []
