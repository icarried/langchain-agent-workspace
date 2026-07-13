from pathlib import Path

from kb_api.rag.ingest import IngestService, _build_default_embeddings, ingest_documents
from kb_api.rag.loaders import DocumentRecord
from kb_api.settings import Settings


class FakeEmbeddings:
    def __init__(self):
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text))] for text in texts]


class FakeCollection:
    def __init__(self):
        self.upserts: list[dict[str, object]] = []

    def upsert(self, *, ids, documents, metadatas, embeddings):
        self.upserts.append(
            {
                "ids": list(ids),
                "documents": list(documents),
                "metadatas": list(metadatas),
                "embeddings": list(embeddings),
            }
        )


def test_ingest_returns_clear_stats_for_empty_directory(tmp_path: Path):
    settings = Settings(chroma_collection="test_collection", docs_dir=tmp_path)
    collection = FakeCollection()
    embeddings = FakeEmbeddings()

    stats = IngestService(
        settings,
        embedding_provider=embeddings,
        collection_factory=lambda _: collection,
    ).ingest()

    assert stats.documents_seen == 0
    assert stats.documents_loaded == 0
    assert stats.chunks_written == 0
    assert stats.collection == "test_collection"
    assert embeddings.calls == []
    assert collection.upserts == []


def test_ingest_skips_unsupported_and_empty_documents(tmp_path: Path):
    (tmp_path / "empty.txt").write_text("   ", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("abcdefghij", encoding="utf-8")
    (tmp_path / "image.png").write_text("ignored", encoding="utf-8")

    settings = Settings(chroma_collection="test_collection", docs_dir=tmp_path)
    collection = FakeCollection()
    embeddings = FakeEmbeddings()

    stats = IngestService(
        settings,
        embedding_provider=embeddings,
        collection_factory=lambda _: collection,
        chunker=lambda docs: [
            DocumentRecord(page_content="abcd", metadata={"source": docs[0].metadata["source"], "chunk_index": 0}),
            DocumentRecord(page_content="efgh", metadata={"source": docs[0].metadata["source"], "chunk_index": 1}),
        ],
    ).ingest()

    assert stats.documents_seen == 3
    assert stats.documents_loaded == 1
    assert stats.chunks_written == 2
    assert embeddings.calls == [["abcd", "efgh"]]
    assert len(collection.upserts) == 1


def test_ingest_uses_stable_ids_for_repeated_runs(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("abcdefghij", encoding="utf-8")
    settings = Settings(chroma_collection="test_collection", docs_dir=tmp_path)

    first_collection = FakeCollection()
    second_collection = FakeCollection()
    embeddings = FakeEmbeddings()

    service = IngestService(
        settings,
        embedding_provider=embeddings,
        collection_factory=lambda _: first_collection,
        chunker=lambda docs: [
            DocumentRecord(page_content="abcd", metadata={"source": docs[0].metadata["source"], "chunk_index": 0}),
            DocumentRecord(page_content="efgh", metadata={"source": docs[0].metadata["source"], "chunk_index": 1}),
        ],
    )
    first_stats = service.ingest()

    second_service = IngestService(
        settings,
        embedding_provider=embeddings,
        collection_factory=lambda _: second_collection,
        chunker=lambda docs: [
            DocumentRecord(page_content="abcd", metadata={"source": docs[0].metadata["source"], "chunk_index": 0}),
            DocumentRecord(page_content="efgh", metadata={"source": docs[0].metadata["source"], "chunk_index": 1}),
        ],
    )
    second_stats = second_service.ingest()

    assert first_stats.chunks_written == second_stats.chunks_written == 2
    assert first_collection.upserts[0]["ids"] == second_collection.upserts[0]["ids"]


def test_ingest_documents_returns_schema_response(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("abcdefghij", encoding="utf-8")
    settings = Settings(chroma_collection="test_collection", docs_dir=tmp_path)
    collection = FakeCollection()
    embeddings = FakeEmbeddings()

    response = ingest_documents(
        settings,
        embedding_provider=embeddings,
        collection_factory=lambda _: collection,
        chunker=lambda docs: [
            DocumentRecord(page_content="abcd", metadata={"source": docs[0].metadata["source"], "chunk_index": 0}),
        ],
    )

    assert response.documents_seen == 1
    assert response.documents_loaded == 1
    assert response.chunks_written == 1
    assert response.collection == "test_collection"


def test_embedding_config_can_use_separate_provider():
    settings = Settings(
        openai_api_key="chat-key",
        openai_base_url="https://api.deepseek.com",
        embedding_api_key="embedding-key",
        embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        embedding_model="text-embedding-v4",
    )

    assert settings.model_configured is True
    assert settings.embedding_configured is True
    assert settings.effective_embedding_api_key == "embedding-key"
    assert settings.effective_embedding_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_default_embedding_client_sends_plain_text_for_compatible_providers():
    settings = Settings(
        embedding_api_key="embedding-key",
        embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        embedding_model="text-embedding-v4",
    )

    embeddings = _build_default_embeddings(settings)

    assert embeddings.tiktoken_enabled is False
    assert embeddings.check_embedding_ctx_length is False
