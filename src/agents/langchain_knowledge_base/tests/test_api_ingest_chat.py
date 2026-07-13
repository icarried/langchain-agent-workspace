from fastapi.testclient import TestClient

from kb_api import main
from kb_api.rag.retriever import Document, RetrievedChunk
from kb_api.schemas import ChatResponse, Citation, IngestResponse


class FakeIngestService:
    def __init__(self):
        self.docs_dir = None

    def ingest(self, docs_dir=None):
        self.docs_dir = docs_dir
        return self

    def to_response(self):
        return IngestResponse(
            documents_seen=1,
            documents_loaded=1,
            chunks_written=2,
            collection="test_collection",
        )


class FakeAnswerService:
    def __init__(self):
        self.calls = []

    def answer(self, question: str, *, top_k: int | None = None):
        self.calls.append((question, top_k))
        return ChatResponse(
            answer="Use Chroma for local vector search.",
            citations=[
                Citation(
                    source="guide.md",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    text="Chroma is the local vector store.",
                    score=0.9,
                )
            ],
            refused=False,
        )


class FakeRetrievalService:
    def __init__(self):
        self.calls = []

    def retrieve(self, question: str, *, top_k: int | None = None):
        self.calls.append((question, top_k))
        return [
            RetrievedChunk(
                document=Document(
                    page_content="Chroma is the local vector store.",
                    metadata={"source": "guide.md", "chunk_id": "chunk-1", "chunk_index": 0},
                ),
                score=0.9,
            )
        ]


def test_ingest_route_uses_ingest_service(monkeypatch):
    fake_service = FakeIngestService()
    monkeypatch.setattr(main, "build_ingest_service", lambda settings: fake_service)

    client = TestClient(main.app)
    response = client.post("/ingest", json={"docs_dir": "data/docs"})

    assert response.status_code == 200
    assert response.json()["chunks_written"] == 2
    assert fake_service.docs_dir == "data/docs"


def test_ingest_route_can_target_named_knowledge_base(monkeypatch):
    fake_service = FakeIngestService()
    seen_collections = []

    def build_service(settings):
        seen_collections.append(settings.chroma_collection)
        return fake_service

    monkeypatch.setattr(main, "build_ingest_service", build_service)

    client = TestClient(main.app)
    response = client.post("/ingest", json={"knowledge_base": "secondary"})

    assert response.status_code == 200
    assert seen_collections == ["knowledge_base_secondary"]


def test_models_route_lists_knowledge_base_model():
    client = TestClient(main.app)

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == main.MODEL_ID


def test_chat_completions_uses_answer_service(monkeypatch):
    fake_service = FakeAnswerService()
    monkeypatch.setenv("KB_OPENAI_API_KEY", "test-key")
    main.get_settings.cache_clear()
    monkeypatch.setattr(main, "build_answer_service", lambda settings: fake_service)

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": main.MODEL_ID,
            "messages": [{"role": "user", "content": "What vector store?"}],
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "Use Chroma for local vector search." in content
    assert "guide.md#chunk-0" in content
    assert fake_service.calls == [("What vector store?", 2)]

    main.get_settings.cache_clear()


def test_chat_completions_returns_readiness_for_generic_probe():
    client = TestClient(main.app)

    response = client.post(
        "/v1/chat/completions",
        json={"model": main.MODEL_ID, "messages": [{"role": "user", "content": ""}], "stream": False},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == main.READINESS_TEXT


def test_streaming_chat_completions_emits_done():
    client = TestClient(main.app)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": main.MODEL_ID, "messages": [{"role": "user", "content": ""}], "stream": True},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "chat.completion.chunk" in body
    assert "data: [DONE]" in body


def test_retrieval_route_returns_citations(monkeypatch):
    fake_service = FakeRetrievalService()
    monkeypatch.setenv("KB_EMBEDDING_API_KEY", "test-key")
    main.get_settings.cache_clear()
    monkeypatch.setattr(main, "build_retrieval_service", lambda settings: fake_service)

    client = TestClient(main.app)
    response = client.post("/v1/retrieval", json={"question": "What vector store?", "top_k": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "What vector store?"
    assert payload["refused"] is False
    assert payload["citations"][0]["source"] == "guide.md"
    assert fake_service.calls == [("What vector store?", 2)]

    main.get_settings.cache_clear()


def test_chat_route_reports_missing_model_config(monkeypatch):
    monkeypatch.setenv("KB_OPENAI_API_KEY", "")
    main.get_settings.cache_clear()

    client = TestClient(main.app)
    response = client.post(
        "/v1/chat/completions",
        json={"model": main.MODEL_ID, "messages": [{"role": "user", "content": "What vector store?"}]},
    )

    assert response.status_code == 503
    assert "KB_OPENAI_API_KEY" in response.json()["detail"]

    main.get_settings.cache_clear()
