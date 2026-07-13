from fastapi.testclient import TestClient

from kb_api import main
from kb_api.main import app
from kb_api.settings import Settings


def test_health_reports_components_without_required_model_config():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api"]["status"] == "ok"
    assert payload["chroma"]["status"] == "ok"
    assert payload["chroma"]["detail"].startswith("persistent:")
    assert payload["model"]["status"] in {"ok", "missing_config"}


def test_health_requires_chat_and_embedding_config(monkeypatch):
    monkeypatch.setenv("KB_OPENAI_API_KEY", "chat-key")
    monkeypatch.setenv("KB_EMBEDDING_API_KEY", "embedding-key")
    main.get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["model"]["status"] == "ok"

    main.get_settings.cache_clear()


def test_ingest_reports_missing_embedding_config(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(openai_api_key="", embedding_api_key="", docs_dir=tmp_path))

    client = TestClient(app)
    response = client.post("/ingest")

    assert response.status_code == 503
    assert "KB_EMBEDDING_API_KEY" in response.json()["detail"]
