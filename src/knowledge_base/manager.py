from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any, Mapping, Protocol

from .loaders import (
    SUPPORTED_EXTENSIONS,
    DocumentRecord,
    chunk_documents,
    iter_supported_paths,
    load_document,
)
from .schemas import (
    Citation,
    IngestResult,
    KnowledgeAnswer,
    KnowledgeBaseInfo,
    MultiQueryRetrievalResult,
    RetrievalResult,
)
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


DocumentLoader = Callable[..., DocumentRecord | None]
ProgressCallback = Callable[[str, str], None]


class KnowledgeBaseManager:
    def __init__(
        self,
        namespace: str,
        *,
        settings: KnowledgeBaseSettings | None = None,
        embeddings: Embeddings | None = None,
        chat_model: ChatModel | None = None,
        document_loader: DocumentLoader | None = None,
        supported_extensions: set[str] | None = None,
    ) -> None:
        self.settings = settings or KnowledgeBaseSettings(namespace=namespace)
        self.namespace = validate_slug(namespace, "namespace")
        self.root = self.settings.data_root / self.namespace
        self._embeddings = embeddings
        self._chat_model = chat_model
        self._document_loader = document_loader or load_document
        self._supported_extensions = supported_extensions or SUPPORTED_EXTENSIONS

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
                    documents_dir=str(self.active_documents_dir(directory.name)),
                    ingested_at=manifest.get("ingested_at"),
                    document_count=len(manifest.get("documents", {})),
                )
            )
        return results

    def ingest(self, knowledge_base: str, *, rebuild: bool = False) -> IngestResult:
        name = validate_slug(knowledge_base, "knowledge base")
        documents = self.documents_dir(name)
        return self._publish_snapshot(
            name,
            source_documents=documents,
            rebuild=rebuild,
        )

    def publish_document_updates(
        self,
        knowledge_base: str,
        documents: Mapping[str, bytes],
        *,
        catalog_updates: Mapping[str, Mapping[str, Any]] | None = None,
        prepared_records: Mapping[str, DocumentRecord] | None = None,
        rebuild: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IngestResult:
        """Build and publish a new immutable snapshot without mutating the active one."""
        name = validate_slug(knowledge_base, "knowledge base")
        base = self._base_path(name)
        base.mkdir(parents=True, exist_ok=True)
        versions = base / "versions"
        versions.mkdir(exist_ok=True)
        source_documents = self.active_documents_dir(name)
        stage = versions / uuid.uuid4().hex
        stage_documents = stage / "documents"
        try:
            if source_documents.exists():
                shutil.copytree(source_documents, stage_documents)
            else:
                stage_documents.mkdir(parents=True)
            for filename, data in documents.items():
                safe_name = Path(filename).name
                if filename != safe_name or "\\" in filename:
                    raise ValueError(f"invalid document filename: {filename!r}")
                target = stage_documents / safe_name
                target.write_bytes(data)
            return self._publish_snapshot(
                name,
                source_documents=stage_documents,
                rebuild=rebuild,
                progress=progress,
                prepared_stage=stage,
                catalog_updates=catalog_updates,
                prepared_records=prepared_records,
                updated_documents=set(documents),
            )
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    def _publish_snapshot(
        self,
        name: str,
        *,
        source_documents: Path,
        rebuild: bool,
        progress: ProgressCallback | None = None,
        prepared_stage: Path | None = None,
        catalog_updates: Mapping[str, Mapping[str, Any]] | None = None,
        prepared_records: Mapping[str, DocumentRecord] | None = None,
        updated_documents: set[str] | None = None,
    ) -> IngestResult:
        base = self._base_path(name)
        base.mkdir(parents=True, exist_ok=True)
        versions = base / "versions"
        versions.mkdir(exist_ok=True)
        stage = prepared_stage or versions / uuid.uuid4().hex
        paths = {
            "base": stage,
            "documents": stage / "documents",
            "chroma": stage / "chroma",
            "manifest": stage / "manifest.json",
        }
        if prepared_stage is None:
            if source_documents.exists():
                shutil.copytree(source_documents, paths["documents"])
            else:
                paths["documents"].mkdir(parents=True)
        fingerprints = {
            path.relative_to(paths["documents"]).as_posix(): _sha256_file(path)
            for path in iter_supported_paths(
                paths["documents"],
                supported_extensions=self._supported_extensions,
            )
        }
        existing = _read_json(base / "manifest.json")
        catalog = _merge_document_catalog(
            existing.get("document_catalog"),
            fingerprints,
            catalog_updates,
        )
        signature = self._embedding_signature()
        if existing and existing.get("embedding_signature") != signature and not rebuild:
            shutil.rmtree(stage, ignore_errors=True)
            raise RebuildRequiredError("embedding configuration changed; ingest again with rebuild=true")
        if (
            existing.get("documents") == fingerprints
            and existing.get("document_catalog", {}) == catalog
            and not rebuild
        ):
            shutil.rmtree(stage, ignore_errors=True)
            return IngestResult(
                knowledge_base=name,
                documents_seen=len(fingerprints),
                documents_loaded=len(fingerprints),
                chunks_written=0,
                unchanged=True,
            )

        incremental = bool(
            existing
            and not rebuild
            and updated_documents is not None
            and existing.get("embedding_signature") == signature
            and self._paths(name)["chroma"].exists()
        )
        changed_documents = {
            filename
            for filename in (updated_documents or set())
            if existing.get("documents", {}).get(filename)
            != fingerprints.get(filename)
        }
        if incremental:
            shutil.copytree(self._paths(name)["chroma"], paths["chroma"])
            if progress:
                progress(
                    "reuse_index",
                    (
                        "已复用当前索引；"
                        f"本次仅更新 {len(changed_documents)} 个变更文档。"
                    ),
                )

        loaded_documents = []
        committed = False
        all_document_paths = iter_supported_paths(
            paths["documents"],
            supported_extensions=self._supported_extensions,
        )
        document_paths = (
            [
                path
                for path in all_document_paths
                if path.relative_to(paths["documents"]).as_posix()
                in changed_documents
            ]
            if incremental
            else all_document_paths
        )
        try:
            for index, path in enumerate(document_paths, start=1):
                if progress:
                    progress(
                        "parse_document",
                        f"正在解析第 {index}/{len(document_paths)} 个文档：{path.name}",
                    )
                relative_name = path.relative_to(paths["documents"]).as_posix()
                document = (
                    prepared_records.get(relative_name)
                    if prepared_records and relative_name in prepared_records
                    else self._document_loader(
                        path,
                        source_root=paths["documents"],
                    )
                )
                if document is not None:
                    loaded_documents.append(document)
                if progress:
                    progress(
                        "parse_document",
                        f"第 {index}/{len(document_paths)} 个文档解析完成：{path.name}",
                    )
            chunks = chunk_documents(loaded_documents)
            if progress:
                progress(
                    "embed",
                    f"正在生成 {len(chunks)} 个新增或变更检索分块的向量。",
                )
            vectors = (
                self._get_embeddings().embed_documents(
                    [chunk.page_content for chunk in chunks]
                )
                if chunks
                else []
            )
            if progress:
                progress("build_index", "正在构建并验证新的 Chroma 索引。")
            backend = _ChromaBackend(paths["chroma"])
            previous_count = backend.count() if incremental else 0
            deleted_count = (
                backend.delete_sources(changed_documents)
                if incremental and changed_documents
                else 0
            )
            if chunks:
                backend.upsert(chunks, vectors)
            expected_count = previous_count - deleted_count + len(chunks)
            if backend.count() != expected_count:
                raise RuntimeError("new Chroma index verification failed")
            version = stage.name
            manifest = {
                "namespace": self.namespace,
                "knowledge_base": name,
                "active_version": version,
                "documents": fingerprints,
                "document_catalog": catalog,
                "ingested_at": datetime.now(UTC).isoformat(),
                "embedding_model": self.settings.embedding_model,
                "embedding_signature": signature,
                "chunk_count": expected_count,
            }
            _write_json(paths["manifest"], manifest)
            try:
                _write_json(base / "manifest.json", manifest)
            except Exception:
                shutil.rmtree(stage, ignore_errors=True)
                raise
            committed = True
            try:
                self._prune_versions(
                    base,
                    active_version=version,
                    previous_version=existing.get("active_version"),
                )
            except Exception:
                # Retention cleanup must never turn a committed publish into failure.
                pass
        except Exception:
            if not committed:
                shutil.rmtree(stage, ignore_errors=True)
            raise
        return IngestResult(
            knowledge_base=name,
            documents_seen=len(fingerprints),
            documents_loaded=len(loaded_documents),
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

    def retrieve_many(
        self,
        knowledge_base: str,
        queries: list[str],
        *,
        top_k: int | None = None,
        max_chunks: int = 20,
        max_documents: int = 10,
        rrf_k: int = 60,
    ) -> MultiQueryRetrievalResult:
        name = validate_slug(knowledge_base, "knowledge base")
        paths = self._paths(name)
        if not paths["manifest"].exists():
            raise FileNotFoundError(f"knowledge base is not ingested: {name}")
        unique_queries = _dedupe_queries(queries)
        if not unique_queries:
            return MultiQueryRetrievalResult(refused=True)
        vectors = self._get_embeddings().embed_documents(unique_queries)
        rows_by_query = _ChromaBackend(paths["chroma"]).query_many(
            vectors,
            top_k or self.settings.top_k,
        )
        fused: dict[str, dict[str, Any]] = {}
        for rows in rows_by_query:
            for rank, row in enumerate(rows, start=1):
                score = row["score"]
                if score < self.settings.min_relevance_score:
                    continue
                entry = fused.setdefault(
                    row["id"],
                    {
                        "row": row,
                        "fusion_score": 0.0,
                        "best_score": score,
                    },
                )
                entry["fusion_score"] += 1.0 / (rrf_k + rank)
                if score > entry["best_score"]:
                    entry["best_score"] = score
                    entry["row"] = row
        ordered = sorted(
            fused.values(),
            key=lambda item: (
                -item["fusion_score"],
                -item["best_score"],
                item["row"]["id"],
            ),
        )
        citations: list[Citation] = []
        documents: set[str] = set()
        for entry in ordered:
            row = entry["row"]
            source = str(row["metadata"].get("source", ""))
            document_key = _document_key(source)
            if document_key not in documents and len(documents) >= max_documents:
                continue
            documents.add(document_key)
            citations.append(
                Citation(
                    source=source,
                    chunk_id=row["id"],
                    chunk_index=int(row["metadata"].get("chunk_index", 0)),
                    text=row["document"][:1000],
                    score=float(entry["best_score"]),
                )
            )
            if len(citations) >= max_chunks:
                break
        return MultiQueryRetrievalResult(
            queries=unique_queries,
            citations=citations,
            refused=not citations,
        )

    def answer(self, knowledge_base: str, query: str, *, top_k: int | None = None) -> KnowledgeAnswer:
        retrieval = self.retrieve(knowledge_base, query, top_k=top_k)
        return self.answer_from_citations(query, retrieval.citations)

    def answer_from_citations(
        self,
        query: str,
        citations: list[Citation],
    ) -> KnowledgeAnswer:
        if not citations:
            return KnowledgeAnswer(answer=REFUSAL_MESSAGE, refused=True)
        context = "\n\n".join(
            f"<evidence source={json.dumps(item.source, ensure_ascii=False)}>\n"
            f"{item.text}\n</evidence>"
            for item in citations
        )
        prompt = (
            "你是企业部门知识库问答助手。请只根据 <context> 中的知识库证据回答用户问题。\n"
            "规则：\n"
            "1. 证据不足时明确说明知识库中没有足够依据；不使用外部常识补全，不编造条款、"
            "数字、文档名或来源。\n"
            "2. 多份证据一致时整合表达；存在冲突时指出冲突及对应文档，不擅自判断真伪。\n"
            "3. 用户问题含多个部分时逐项回答；无法回答的部分单独说明。\n"
            "4. 不要提及“上下文”“向量”“chunk”“检索分块”等内部实现。\n"
            "5. 不要在正文自行生成“来源”段；来源由服务端根据实际证据统一附加。\n"
            "6. 使用与用户问题相同的语言，表达清晰、直接。\n\n"
            f"<context>\n{context}\n</context>\n\n用户问题：\n{query}"
        )
        response = self._get_chat_model().invoke(prompt)
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        return KnowledgeAnswer(answer=content.strip(), citations=citations)

    def documents_dir(self, knowledge_base: str) -> Path:
        name = validate_slug(knowledge_base, "knowledge base")
        path = self._base_path(name) / "documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def active_documents_dir(self, knowledge_base: str) -> Path:
        name = validate_slug(knowledge_base, "knowledge base")
        return self._paths(name)["documents"]

    def active_manifest(self, knowledge_base: str) -> dict[str, Any]:
        name = validate_slug(knowledge_base, "knowledge base")
        return _read_json(self._base_path(name) / "manifest.json")

    def load_document_record(
        self,
        path: Path,
        *,
        source_root: Path,
    ) -> DocumentRecord | None:
        return self._document_loader(path, source_root=source_root)

    def _base_path(self, name: str) -> Path:
        return self.root / name

    def _paths(self, name: str) -> dict[str, Path]:
        base = self._base_path(name)
        manifest = base / "manifest.json"
        active_version = _read_json(manifest).get("active_version")
        snapshot = (
            base / "versions" / active_version
            if isinstance(active_version, str)
            and re.fullmatch(r"[0-9a-f]{32}", active_version)
            else base
        )
        return {
            "base": snapshot,
            "documents": snapshot / "documents",
            "chroma": snapshot / "chroma",
            "manifest": manifest,
        }

    def _prune_versions(
        self,
        base: Path,
        *,
        active_version: str,
        previous_version: object = None,
    ) -> None:
        versions = base / "versions"
        candidates = sorted(
            (
                path
                for path in versions.iterdir()
                if path.is_dir() and re.fullmatch(r"[0-9a-f]{32}", path.name)
            ),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        keep = {active_version}
        if (
            self.settings.version_retention > 1
            and isinstance(previous_version, str)
            and re.fullmatch(r"[0-9a-f]{32}", previous_version)
        ):
            keep.add(previous_version)
        for path in candidates:
            if len(keep) >= self.settings.version_retention:
                break
            keep.add(path.name)
        for path in candidates:
            if path.name not in keep:
                shutil.rmtree(path, ignore_errors=True)

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
        from chromadb.config import Settings

        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False),
        )
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
        documents = [chunk.page_content for chunk in chunks]
        for start in range(0, len(ids), 500):
            stop = start + 500
            collection.upsert(
                ids=ids[start:stop],
                documents=documents[start:stop],
                metadatas=metadatas[start:stop],
                embeddings=vectors[start:stop],
            )

    def count(self) -> int:
        try:
            collection = self.client.get_collection(self.collection_name)
        except Exception as exc:
            if "does not exist" in str(exc).lower() or "not found" in str(exc).lower():
                return 0
            raise
        return collection.count()

    def delete_sources(self, sources: set[str]) -> int:
        if not sources:
            return 0
        try:
            collection = self.client.get_collection(self.collection_name)
        except Exception as exc:
            if "does not exist" in str(exc).lower() or "not found" in str(exc).lower():
                return 0
            raise
        ids: list[str] = []
        for source in sorted(sources):
            result = collection.get(where={"source": source})
            ids.extend(str(item) for item in (result.get("ids") or []))
        unique_ids = list(dict.fromkeys(ids))
        for start in range(0, len(unique_ids), 500):
            collection.delete(ids=unique_ids[start : start + 500])
        return len(unique_ids)

    def query(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        return self.query_many([vector], top_k)[0]

    def query_many(
        self,
        vectors: list[list[float]],
        top_k: int,
    ) -> list[list[dict[str, Any]]]:
        collection = self.client.get_or_create_collection(self.collection_name)
        result = collection.query(query_embeddings=vectors, n_results=top_k)
        all_ids = result.get("ids") or [[] for _ in vectors]
        all_documents = result.get("documents") or [[] for _ in vectors]
        all_metadatas = result.get("metadatas") or [[] for _ in vectors]
        all_distances = result.get("distances") or [[] for _ in vectors]
        return [
            [
                {
                    "id": chunk_id,
                    "document": document,
                    "metadata": metadata or {},
                    "score": max(0.0, min(1.0, 1.0 - float(distance))),
                }
                for chunk_id, document, metadata, distance in zip(
                    ids,
                    documents,
                    metadatas,
                    distances,
                )
            ]
            for ids, documents, metadatas, distances in zip(
                all_ids,
                all_documents,
                all_metadatas,
                all_distances,
            )
        ]


def validate_slug(value: str, label: str) -> str:
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {label} slug: {value!r}")
    return value


def _dedupe_queries(queries: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = " ".join(query.split()).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _document_key(source: str) -> str:
    name = Path(source.replace("\\", "/")).name
    return unicodedata.normalize("NFC", name).casefold()


def _merge_document_catalog(
    existing: object,
    fingerprints: Mapping[str, str],
    updates: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    existing_catalog = existing if isinstance(existing, dict) else {}
    update_catalog = updates or {}
    result: dict[str, dict[str, Any]] = {}
    for filename, digest in fingerprints.items():
        value: dict[str, Any] = {}
        previous = existing_catalog.get(filename)
        if isinstance(previous, dict):
            value.update(previous)
        update = update_catalog.get(filename)
        if isinstance(update, Mapping):
            value.update(
                {
                    str(key): item
                    for key, item in update.items()
                    if item is not None
                }
            )
        value["sha256"] = digest
        result[filename] = value
    return result


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
