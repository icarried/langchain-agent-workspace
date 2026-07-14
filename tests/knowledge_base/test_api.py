from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.langchain_knowledge_base import openai_compatible_api as api
from src.knowledge_base.manager import KnowledgeBaseManager
from src.knowledge_base.settings import KnowledgeBaseSettings


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


class FakeChat:
    def invoke(self, value):
        return "answer"


def _configure(tmp_path: Path, monkeypatch):
    settings = KnowledgeBaseSettings(data_root=tmp_path, namespace=api.MODEL_ID, min_relevance_score=0)
    manager = KnowledgeBaseManager(
        api.MODEL_ID, settings=settings, embeddings=FakeEmbeddings(), chat_model=FakeChat()
    )
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(api, "manager", manager)
    return manager


def test_models_and_provider_probe_readiness(tmp_path: Path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    client = TestClient(api.app)
    assert client.get("/v1/models").json()["data"][0]["id"] == api.MODEL_ID
    response = client.post(
        "/v1/chat/completions",
        json={"model": api.MODEL_ID, "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert "已就绪" in response.json()["choices"][0]["message"]["content"]


def test_management_and_streaming_chat(tmp_path: Path, monkeypatch):
    manager = _configure(tmp_path, monkeypatch)
    (manager.documents_dir("default") / "guide.md").write_text("knowledge", encoding="utf-8")
    client = TestClient(api.app)
    ingest = client.post("/v1/knowledge-bases/default/ingest", json={})
    assert ingest.status_code == 200
    assert client.get("/v1/knowledge-bases").json()["data"][0]["name"] == "default"
    retrieval = client.post(
        "/v1/knowledge-bases/default/retrieval", json={"question": "knowledge"}
    )
    assert retrieval.status_code == 200
    stream = client.post(
        "/v1/chat/completions",
        json={
            "model": api.MODEL_ID,
            "messages": [{"role": "user", "content": "knowledge"}],
            "stream": True,
        },
    )
    assert stream.status_code == 200
    assert "data: [DONE]" in stream.text
