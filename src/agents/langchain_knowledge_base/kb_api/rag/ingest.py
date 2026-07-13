from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Protocol

from kb_api.rag.chunking import chunk_documents
from kb_api.rag.loaders import DocumentRecord, UnsupportedDocumentError, iter_document_paths, load_document
from kb_api.schemas import IngestResponse
from kb_api.settings import Settings


class EmbeddingsProtocol(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...


class CollectionProtocol(Protocol):
    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> Any:
        ...


@dataclass(slots=True)
class IngestStats:
    documents_seen: int
    documents_loaded: int
    chunks_written: int
    collection: str

    def to_response(self) -> IngestResponse:
        return IngestResponse(
            documents_seen=self.documents_seen,
            documents_loaded=self.documents_loaded,
            chunks_written=self.chunks_written,
            collection=self.collection,
        )


class IngestService:
    def __init__(
        self,
        settings: Settings,
        *,
        embedding_provider: EmbeddingsProtocol | Callable[[list[str]], list[list[float]]] | None = None,
        collection_factory: Callable[[Settings], CollectionProtocol] | None = None,
        chunker: Callable[[list[DocumentRecord]], list[DocumentRecord]] = chunk_documents,
    ) -> None:
        self._settings = settings
        self._embedding_provider = embedding_provider or _build_default_embeddings(settings)
        self._collection_factory = collection_factory or _build_default_collection
        self._chunker = chunker

    def ingest(self, docs_dir: str | Path | None = None) -> IngestStats:
        root = Path(docs_dir or self._settings.docs_dir)
        paths = list(iter_document_paths(root))
        documents = self._load_supported_documents(paths)

        if not documents:
            return IngestStats(
                documents_seen=len(paths),
                documents_loaded=0,
                chunks_written=0,
                collection=self._settings.chroma_collection,
            )

        chunks = self._chunker(documents)
        if not chunks:
            return IngestStats(
                documents_seen=len(paths),
                documents_loaded=len(documents),
                chunks_written=0,
                collection=self._settings.chroma_collection,
            )

        texts = [chunk.page_content for chunk in chunks]
        ids = [_stable_chunk_id(chunk) for chunk in chunks]
        metadatas = []
        for chunk, chunk_id in zip(chunks, ids):
            metadata = dict(chunk.metadata)
            metadata["chunk_id"] = chunk_id
            metadatas.append(metadata)
        embeddings = _embed_texts(self._embedding_provider, texts)

        collection = self._collection_factory(self._settings)
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)

        return IngestStats(
            documents_seen=len(paths),
            documents_loaded=len(documents),
            chunks_written=len(chunks),
            collection=self._settings.chroma_collection,
        )

    def _load_supported_documents(self, paths: list[Path]) -> list[DocumentRecord]:
        documents: list[DocumentRecord] = []
        for path in paths:
            try:
                document = load_document(path)
            except UnsupportedDocumentError:
                continue

            if document is not None:
                documents.append(document)

        return documents


def ingest_documents(
    settings: Settings,
    *,
    docs_dir: str | Path | None = None,
    embedding_provider: EmbeddingsProtocol | Callable[[list[str]], list[list[float]]] | None = None,
    collection_factory: Callable[[Settings], CollectionProtocol] | None = None,
    chunker: Callable[[list[DocumentRecord]], list[DocumentRecord]] = chunk_documents,
) -> IngestResponse:
    service = IngestService(
        settings,
        embedding_provider=embedding_provider,
        collection_factory=collection_factory,
        chunker=chunker,
    )
    return service.ingest(docs_dir).to_response()


def _embed_texts(
    embedding_provider: EmbeddingsProtocol | Callable[[list[str]], list[list[float]]],
    texts: list[str],
) -> list[list[float]]:
    if hasattr(embedding_provider, "embed_documents"):
        return embedding_provider.embed_documents(texts)
    return embedding_provider(texts)


def _stable_chunk_id(chunk: DocumentRecord) -> str:
    source = str(chunk.metadata.get("source", ""))
    chunk_index = str(chunk.metadata.get("chunk_index", 0))
    digest = sha1(f"{source}:{chunk_index}:{chunk.page_content}".encode("utf-8")).hexdigest()
    return digest


def _build_default_embeddings(settings: Settings) -> EmbeddingsProtocol:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.effective_embedding_api_key,
        base_url=settings.effective_embedding_base_url,
        tiktoken_enabled=False,
        check_embedding_ctx_length=False,
    )


def _build_default_collection(settings: Settings) -> CollectionProtocol:
    import chromadb

    client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    return client.get_or_create_collection(name=settings.chroma_collection)
