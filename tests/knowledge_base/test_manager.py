from pathlib import Path

import pytest

from src.knowledge_base import manager as manager_module
from src.knowledge_base.manager import KnowledgeBaseManager, RebuildRequiredError
from src.knowledge_base.settings import KnowledgeBaseSettings


class FakeEmbeddings:
    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(list(texts))
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float("vector" in lowered), float("policy" in lowered), 1.0]


class FailingEmbeddings(FakeEmbeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


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


def test_failed_update_keeps_previous_snapshot_and_manifest(tmp_path: Path):
    manager = _manager(tmp_path)
    (manager.documents_dir("default") / "guide.txt").write_text(
        "vector policy",
        encoding="utf-8",
    )
    manager.ingest("default")
    manifest = (tmp_path / "agent-a" / "default" / "manifest.json").read_text(
        encoding="utf-8"
    )
    active_documents = manager.active_documents_dir("default")

    manager._embeddings = FailingEmbeddings()
    with pytest.raises(RuntimeError, match="embedding failed"):
        manager.publish_document_updates(
            "default",
            {"new.txt": b"new vector policy"},
        )

    assert (tmp_path / "agent-a" / "default" / "manifest.json").read_text(
        encoding="utf-8"
    ) == manifest
    assert manager.active_documents_dir("default") == active_documents
    assert (active_documents / "guide.txt").exists()
    assert not (active_documents / "new.txt").exists()


def test_successful_update_publishes_complete_document_snapshot(tmp_path: Path):
    manager = _manager(tmp_path)
    (manager.documents_dir("default") / "guide.txt").write_text(
        "vector policy",
        encoding="utf-8",
    )
    manager.ingest("default")

    result = manager.publish_document_updates(
        "default",
        {"new.txt": b"new vector policy"},
    )
    active_documents = manager.active_documents_dir("default")

    assert result.documents_seen == 2
    assert (active_documents / "guide.txt").exists()
    assert (active_documents / "new.txt").read_bytes() == b"new vector policy"
    assert "versions" in active_documents.parts


def test_update_reuses_unchanged_index_and_only_embeds_changed_document(
    tmp_path: Path,
):
    manager = _manager(tmp_path)
    embeddings = manager._embeddings
    (manager.documents_dir("default") / "guide.txt").write_text(
        "existing policy",
        encoding="utf-8",
    )
    manager.ingest("default")
    embeddings.document_batches.clear()
    progress: list[tuple[str, str]] = []

    result = manager.publish_document_updates(
        "default",
        {"new.txt": b"new vector policy"},
        progress=lambda stage, message: progress.append((stage, message)),
    )

    assert result.documents_seen == 2
    assert result.documents_loaded == 1
    assert embeddings.document_batches == [["new vector policy"]]
    assert any(stage == "reuse_index" for stage, _message in progress)
    assert not any("第 1/2 个文档" in message for _stage, message in progress)
    assert manager.active_manifest("default")["chunk_count"] == 2


def test_replacing_document_removes_its_previous_chunks(tmp_path: Path):
    manager = _manager(tmp_path)
    (manager.documents_dir("default") / "guide.txt").write_text(
        "old policy",
        encoding="utf-8",
    )
    manager.ingest("default")

    manager.publish_document_updates(
        "default",
        {"guide.txt": b"new vector policy"},
    )

    active = manager.active_manifest("default")
    assert active["chunk_count"] == 1
    retrieval = manager.retrieve("default", "vector policy", top_k=5)
    assert [citation.text for citation in retrieval.citations] == [
        "new vector policy"
    ]


def test_retrieve_many_uses_rrf_deduplicates_chunks_and_limits_documents(
    tmp_path: Path,
    monkeypatch,
):
    manager = _manager(tmp_path)
    base = tmp_path / "agent-a" / "default"
    base.mkdir(parents=True)
    (base / "manifest.json").write_text("{}", encoding="utf-8")

    rows = [
        [
            {
                "id": "shared",
                "document": "共同证据",
                "metadata": {"source": "制度A.pdf", "chunk_index": 0},
                "score": 0.8,
            },
            {
                "id": "only-a",
                "document": "证据A",
                "metadata": {"source": "制度B.pdf", "chunk_index": 0},
                "score": 0.9,
            },
        ],
        [
            {
                "id": "shared",
                "document": "共同证据",
                "metadata": {"source": "制度A.pdf", "chunk_index": 0},
                "score": 0.95,
            },
            {
                "id": "only-b",
                "document": "证据B",
                "metadata": {"source": "制度C.pdf", "chunk_index": 0},
                "score": 0.85,
            },
        ],
    ]

    class FakeBackend:
        def __init__(self, _path):
            pass

        def query_many(self, vectors, top_k):
            assert len(vectors) == 2
            assert top_k == 5
            return rows

    monkeypatch.setattr(manager_module, "_ChromaBackend", FakeBackend)

    result = manager.retrieve_many(
        "default",
        ["采购验收", "采购 验收"],
        top_k=5,
        max_chunks=3,
        max_documents=2,
        rrf_k=60,
    )

    assert result.queries == ["采购验收", "采购 验收"]
    assert [item.chunk_id for item in result.citations] == ["shared", "only-a"]
    assert result.citations[0].score == 0.95
    assert len({item.source for item in result.citations}) == 2
