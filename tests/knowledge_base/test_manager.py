from pathlib import Path

import pytest

from src.knowledge_base.manager import KnowledgeBaseManager, RebuildRequiredError
from src.knowledge_base.settings import KnowledgeBaseSettings


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float("vector" in lowered), float("policy" in lowered), 1.0]


class FakeResponse:
    content = "基于知识库的回答"


class FakeChat:
    def invoke(self, value):
        assert "证据" in value
        return FakeResponse()


def _manager(tmp_path: Path, namespace: str = "agent-a", **updates) -> KnowledgeBaseManager:
    settings = KnowledgeBaseSettings(
        data_root=tmp_path,
        namespace=namespace,
        min_relevance_score=0,
        embedding_model=updates.pop("embedding_model", "fake-v1"),
        **updates,
    )
    return KnowledgeBaseManager(namespace, settings=settings, embeddings=FakeEmbeddings(), chat_model=FakeChat())


def test_namespaces_and_knowledge_bases_have_isolated_storage(tmp_path: Path):
    first = _manager(tmp_path, "agent-a")
    second = _manager(tmp_path, "agent-b")
    assert first.documents_dir("manual") == tmp_path / "agent-a" / "manual" / "documents"
    assert second.documents_dir("manual") == tmp_path / "agent-b" / "manual" / "documents"


@pytest.mark.parametrize("value", ["../escape", "UPPER", "has space", "", "a/b"])
def test_invalid_slugs_are_rejected(tmp_path: Path, value: str):
    with pytest.raises(ValueError):
        _manager(tmp_path, value)


def test_ingest_is_idempotent_and_writes_manifest(tmp_path: Path):
    manager = _manager(tmp_path)
    documents = manager.documents_dir("default")
    (documents / "guide.md").write_text("Vector database policy and operating guide.", encoding="utf-8")

    first = manager.ingest("default")
    second = manager.ingest("default")

    assert first.documents_loaded == 1
    assert first.chunks_written == 1
    assert second.unchanged is True
    assert second.chunks_written == 0
    assert (tmp_path / "agent-a" / "default" / "manifest.json").exists()
    assert manager.list_knowledge_bases()[0].document_count == 1


def test_embedding_change_requires_explicit_rebuild(tmp_path: Path):
    first = _manager(tmp_path, embedding_model="fake-v1")
    (first.documents_dir("default") / "guide.txt").write_text("vector policy", encoding="utf-8")
    first.ingest("default")

    changed = _manager(tmp_path, embedding_model="fake-v2")
    with pytest.raises(RebuildRequiredError):
        changed.ingest("default")
    rebuilt = changed.ingest("default", rebuild=True)
    assert rebuilt.chunks_written == 1


def test_retrieve_answer_and_refusal(tmp_path: Path):
    manager = _manager(tmp_path)
    (manager.documents_dir("default") / "guide.txt").write_text("vector policy", encoding="utf-8")
    manager.ingest("default")

    retrieval = manager.retrieve("default", "vector policy")
    answer = manager.answer("default", "vector policy")
    assert retrieval.citations[0].source == "guide.txt"
    assert answer.answer == "基于知识库的回答"
    assert answer.citations

    with pytest.raises(FileNotFoundError):
        manager.retrieve("missing", "question")
