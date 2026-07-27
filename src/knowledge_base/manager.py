from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .loaders import DocumentRecord, chunk_documents, iter_supported_paths, load_document
from .schemas import Citation, IngestResult, KnowledgeAnswer, KnowledgeBaseInfo, RetrievalResult
from .settings import KnowledgeBaseSettings


SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
REFUSAL_MESSAGE = "知识库中没有足够证据回答该问题。"


class RebuildRequiredError(RuntimeError):
    pass


class Embeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    def invoke(self, value: Any) -> Any: ...


class KnowledgeBaseManager:
    def __init__(
        self,
        namespace: str,
        *,
        settings: KnowledgeBaseSettings | None = None,
        embeddings: Embeddings | None = None,
        chat_model: ChatModel | None = None,
    ) -> None:
        self.settings = settings or KnowledgeBaseSettings(namespace=namespace)
        self.namespace = validate_slug(namespace, "namespace")
        self.root = self.settings.data_root / self.namespace
        self._embeddings = embeddings
        self._chat_model = chat_model

    def list_knowledge_bases(self) -> list[KnowledgeBaseInfo]:
        if not self.root.exists():
            return []
        results = []
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir() and SLUG_PATTERN.fullmatch(path.name)):
            manifest = _read_json(directory / "manifest.json")
            results.append(
                KnowledgeBaseInfo(
                    name=directory.name,
                    namespace=self.namespace,
                    documents_dir=str(directory / "documents"),
                    ingested_at=manifest.get("ingested_at"),
                    document_count=len(manifest.get("documents", {})),
                )
            )
        return results

    def ingest(self, knowledge_base: str, *, rebuild: bool = False) -> IngestResult:
        name = validate_slug(knowledge_base, "knowledge base")
        paths = self._paths(name)
        paths["documents"].mkdir(parents=True, exist_ok=True)
        fingerprints = {
            path.relative_to(paths["documents"]).as_posix(): _sha256_file(path)
            for path in iter_supported_paths(paths["documents"])
        }
        existing = _read_json(paths["manifest"])
        signature = self._embedding_signature()
        if existing and existing.get("embedding_signature") != signature and not rebuild:
            raise RebuildRequiredError("embedding configuration changed; ingest again with rebuild=true")
        if existing.get("documents") == fingerprints and not rebuild:
            return IngestResult(
                knowledge_base=name,
                documents_seen=len(fingerprints),
                documents_loaded=len(fingerprints),
                chunks_written=0,
                unchanged=True,
            )

        documents = [
            document
            for path in iter_supported_paths(paths["documents"])
            if (document := load_document(path, source_root=paths["documents"])) is not None
        ]
        chunks = chunk_documents(documents)
        embeddings = self._get_embeddings()
        vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks]) if chunks else []
        backend = _ChromaBackend(paths["chroma"])
        backend.reset()
        if chunks:
            backend.upsert(chunks, vectors)
        manifest = {
            "namespace": self.namespace,
            "knowledge_base": name,
            "documents": fingerprints,
            "ingested_at": datetime.now(UTC).isoformat(),
            "embedding_model": self.settings.embedding_model,
            "embedding_signature": signature,
        }
        _write_json(paths["manifest"], manifest)
        return IngestResult(
            knowledge_base=name,
            documents_seen=len(fingerprints),
            documents_loaded=len(documents),
            chunks_written=len(chunks),
        )

    def retrieve(self, knowledge_base: str, query: str, *, top_k: int | None = None) -> RetrievalResult:
        name = validate_slug(knowledge_base, "knowledge base")
        paths = self._paths(name)
        if not paths["manifest"].exists():
            raise FileNotFoundError(f"knowledge base is not ingested: {name}")
        vector = self._get_embeddings().embed_query(query)
        rows = _ChromaBackend(paths["chroma"]).query(vector, top_k or self.settings.top_k)
        citations = [
            Citation(
                source=str(row["metadata"].get("source", "")),
                chunk_id=row["id"],
                chunk_index=int(row["metadata"].get("chunk_index", 0)),
                text=row["document"][:1000],
                score=row["score"],
            )
            for row in rows
            if row["score"] >= self.settings.min_relevance_score
        ]
        return RetrievalResult(query=query, citations=citations, refused=not citations)

    def answer(self, knowledge_base: str, query: str, *, top_k: int | None = None) -> KnowledgeAnswer:
        retrieval = self.retrieve(knowledge_base, query, top_k=top_k)
        if not retrieval.citations:
            return KnowledgeAnswer(answer=REFUSAL_MESSAGE, refused=True)
        context = "\n\n".join(
            f"[{item.source}#chunk-{item.chunk_index}]\n{item.text}" for item in retrieval.citations
        )
        prompt = (
            "请只根据下列知识库证据回答问题；证据不足时明确拒答。"
            "回答后不要编造来源。\n\n"
            f"问题：{query}\n\n证据：\n{context}"
        )
        response = self._get_chat_model().invoke(prompt)
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        return KnowledgeAnswer(answer=content.strip(), citations=retrieval.citations)

    def documents_dir(self, knowledge_base: str) -> Path:
        name = validate_slug(knowledge_base, "knowledge base")
        path = self._paths(name)["documents"]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _paths(self, name: str) -> dict[str, Path]:
        base = self.root / name
        return {
            "base": base,
            "documents": base / "documents",
            "chroma": base / "chroma",
            "manifest": base / "manifest.json",
        }

    def _embedding_signature(self) -> str:
        value = f"{self.settings.effective_embedding_base_url}|{self.settings.embedding_model}"
        return hashlib.sha256(value.encode()).hexdigest()

    def _get_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            if not self.settings.effective_embedding_api_key:
                raise RuntimeError("KB_EMBEDDING_API_KEY or KB_OPENAI_API_KEY is not configured")
            from langchain_openai import OpenAIEmbeddings

            self._embeddings = OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.effective_embedding_api_key,
                base_url=self.settings.effective_embedding_base_url,
                tiktoken_enabled=False,
                check_embedding_ctx_length=False,
            )
        return self._embeddings

    def _get_chat_model(self) -> ChatModel:
        if self._chat_model is None:
            if not self.settings.effective_openai_api_key:
                raise RuntimeError("KB_OPENAI_API_KEY or GPU_STACK_API_KEY is not configured")
            from langchain_openai import ChatOpenAI

            self._chat_model = ChatOpenAI(
                model=self.settings.chat_model,
                api_key=self.settings.effective_openai_api_key,
                base_url=self.settings.openai_base_url,
                temperature=0,
            )
        return self._chat_model


class _ChromaBackend:
    def __init__(self, path: Path) -> None:
        import chromadb

        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection_name = "chunks"

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as exc:
            if "does not exist" not in str(exc).lower() and "not found" not in str(exc).lower():
                raise

    def upsert(self, chunks: list[DocumentRecord], vectors: list[list[float]]) -> None:
        collection = self.client.get_or_create_collection(self.collection_name)
        ids = []
        metadatas = []
        for chunk in chunks:
            identity = f"{chunk.metadata.get('source')}:{chunk.metadata.get('chunk_index')}:{chunk.page_content}"
            chunk_id = hashlib.sha256(identity.encode()).hexdigest()
            ids.append(chunk_id)
            metadata = dict(chunk.metadata)
            metadata["chunk_id"] = chunk_id
            metadatas.append(metadata)
        collection.upsert(
            ids=ids,
            documents=[chunk.page_content for chunk in chunks],
            metadatas=metadatas,
            embeddings=vectors,
        )

    def query(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        collection = self.client.get_or_create_collection(self.collection_name)
        result = collection.query(query_embeddings=[vector], n_results=top_k)
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            {
                "id": chunk_id,
                "document": document,
                "metadata": metadata or {},
                "score": max(0.0, min(1.0, 1.0 - float(distance))),
            }
            for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances)
        ]


def validate_slug(value: str, label: str) -> str:
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {label} slug: {value!r}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
