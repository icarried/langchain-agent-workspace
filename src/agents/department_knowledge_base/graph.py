from __future__ import annotations

import hashlib
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.openai_compatible_inputs import AttachmentReference
from src.document_ocr import GPUStackPaddleOCRVL, OCRProvider
from src.knowledge_base.manager import KnowledgeBaseManager
from src.knowledge_base.loaders import DocumentRecord
from src.knowledge_base.settings import KnowledgeBaseSettings

from .constants import MODEL_ID
from .departments import Department, get_department
from .document_loader import (
    AdaptiveDocumentLoader,
    SUPPORTED_EXTENSIONS,
    document_progress,
)
from .intent import (
    IntentRecognizer,
    QwenIntentRecognizer,
    recognize_intent_dry_run,
)
from .import_tasks import ImportTask, ImportTaskCoordinator
from .object_store import DepartmentObjectStore, MinioDepartmentObjectStore
from .query_rewrite import (
    DeepSeekQueryRewriter,
    QueryRewriteError,
    QueryRewriter,
    merge_original_query,
)
from .schemas import (
    AgentResult,
    Intent,
    IntentDecision,
    ProgressCallback,
    ProgressEvent,
    SourceDocument,
)
from .settings import DepartmentKnowledgeBaseSettings
from .storage import PreparedDocument, prepare_sources


class DepartmentKnowledgeBaseState(TypedDict, total=False):
    knowledge_id: str
    text: str
    sources: list[AttachmentReference]
    top_k: int | None
    dry_run: bool
    department: Department
    decision: IntentDecision
    result: AgentResult
    progress: ProgressCallback | None


class DepartmentKnowledgeBaseRuntime:
    def __init__(
        self,
        *,
        settings: DepartmentKnowledgeBaseSettings | None = None,
        manager: KnowledgeBaseManager | None = None,
        intent_recognizer: IntentRecognizer | None = None,
        query_rewriter: QueryRewriter | None = None,
        ocr_provider: OCRProvider | None = None,
        object_store: DepartmentObjectStore | None = None,
    ) -> None:
        self.settings = settings or DepartmentKnowledgeBaseSettings()
        self._manager = manager
        self._intent_recognizer = intent_recognizer
        self._query_rewriter = query_rewriter
        self._ocr_provider = ocr_provider
        self._object_store = object_store
        self._import_tasks: ImportTaskCoordinator | None = None
        self._locks = {
            knowledge_id: threading.Lock() for knowledge_id in get_department_ids()
        }

    @property
    def manager(self) -> KnowledgeBaseManager:
        if self._manager is None:
            ocr = self._ocr_provider or GPUStackPaddleOCRVL(
                model=self.settings.ocr_model,
                timeout=self.settings.ocr_timeout_seconds,
            )
            kb_settings = KnowledgeBaseSettings(namespace=MODEL_ID)
            self._manager = KnowledgeBaseManager(
                MODEL_ID,
                settings=kb_settings,
                document_loader=AdaptiveDocumentLoader(ocr, self.settings),
                supported_extensions=SUPPORTED_EXTENSIONS,
            )
        return self._manager

    @property
    def intent_recognizer(self) -> IntentRecognizer:
        if self._intent_recognizer is None:
            self._intent_recognizer = QwenIntentRecognizer(self.settings)
        return self._intent_recognizer

    @property
    def object_store(self) -> DepartmentObjectStore | None:
        if not self.settings.object_store_enabled:
            return None
        if self._object_store is None:
            self._object_store = MinioDepartmentObjectStore(self.settings)
        return self._object_store

    @property
    def query_rewriter(self) -> QueryRewriter:
        if self._query_rewriter is None:
            self._query_rewriter = DeepSeekQueryRewriter(self.settings)
        return self._query_rewriter

    @property
    def import_tasks(self) -> ImportTaskCoordinator:
        if self._import_tasks is None:
            self._import_tasks = ImportTaskCoordinator(
                self.manager.root,
                processor=self._process_import_task,
                max_workers=self.settings.import_task_workers,
                retention_days=self.settings.import_task_retention_days,
            )
            self._import_tasks.recover()
        return self._import_tasks

    def save(
        self,
        department: Department,
        sources: list[str | AttachmentReference],
        *,
        progress: ProgressCallback | None = None,
    ) -> AgentResult:
        if not sources:
            return self.result(
                department,
                Intent.SAVE,
                "已识别为保存意图，但没有收到附件。请上传文件并明确说明“保存到知识库”。",
            )
        if len(sources) > self.settings.max_files_per_request:
            raise ValueError(
                f"too many files; maximum is {self.settings.max_files_per_request}"
            )
        task = self.import_tasks.create(department.knowledge_id, sources)
        accepted = (
            f"批量导入任务已受理，任务编号：{task.task_id}。"
            f"共 {len(task.files)} 份文件。"
        )
        if not progress:
            return self.result(
                department,
                Intent.SAVE,
                accepted,
                task_id=task.task_id,
                task_status=task.status,
            )
        progress(ProgressEvent("queued", accepted))
        terminal = self.import_tasks.wait(task.task_id, progress=progress)
        return self._task_result(department, terminal)

    def _process_import_task(
        self,
        task_id: str,
        sources: list[str | AttachmentReference] | None,
    ) -> None:
        task = self.import_tasks.get(task_id)
        if task is None:
            return
        department = get_department(task.knowledge_id)
        try:
            prepared, records, duplicate_of = self._stage_and_parse_task(
                task,
                sources,
            )
            if not prepared:
                self.import_tasks.set_status(
                    task_id,
                    "failed",
                    "没有可发布的有效文件，当前知识库保持不变。",
                )
                return
            self.import_tasks.set_status(
                task_id,
                "publishing",
                f"正在原子发布 {len(prepared)} 份有效文件。",
            )
            with self._locks[department.knowledge_id]:
                ingestion = self.manager.publish_document_updates(
                    department.knowledge_id,
                    {item.filename: item.data for item in prepared.values()},
                    catalog_updates={
                        item.filename: {
                            "size": len(item.data),
                            "mime_type": item.mime_type,
                            "source_kind": item.source_kind,
                        }
                        for item in prepared.values()
                    },
                    prepared_records=records,
                    progress=lambda stage, message: self.import_tasks.emit(
                        task_id,
                        stage,
                        message,
                    ),
                )
            for index in prepared:
                self.import_tasks.update_file(
                    task_id,
                    index,
                    status="published",
                    message=f"已发布：{prepared[index].filename}",
                )
            for index, original_index in duplicate_of.items():
                original = self.import_tasks.get(task_id)
                original_status = (
                    original.files[original_index].status if original else "failed"
                )
                self.import_tasks.update_file(
                    task_id,
                    index,
                    status="published" if original_status == "published" else "failed",
                    message=(
                        f"幂等文件已发布：{task.files[index].filename}"
                        if original_status == "published"
                        else f"幂等文件未发布：{task.files[index].filename}"
                    ),
                    error=(
                        None
                        if original_status == "published"
                        else "对应的首份文件处理失败"
                    ),
                )
            final = self.import_tasks.get(task_id)
            failed_count = final.failed_count if final else 0
            status = "partial" if failed_count else "completed"
            manifest = self.manager.active_manifest(department.knowledge_id)
            self.import_tasks.set_status(
                task_id,
                status,
                (
                    f"导入完成：发布 {len(prepared)} 份，失败 {failed_count} 份。"
                    if failed_count
                    else f"导入完成：发布 {len(prepared)} 份文件。"
                ),
                final_version=(
                    manifest.get("active_version")
                    if isinstance(manifest.get("active_version"), str)
                    else None
                ),
            )
            if ingestion.unchanged:
                self.import_tasks.emit(
                    task_id,
                    "publishing",
                    "文档内容和目录未变化，当前索引保持不变。",
                )
        except Exception as exc:
            self.import_tasks.set_status(
                task_id,
                "failed",
                f"导入失败，当前知识库保持不变：{_safe_error(exc)}",
            )

    def _stage_and_parse_task(
        self,
        task: ImportTask,
        sources: list[str | AttachmentReference] | None,
    ) -> tuple[
        dict[int, PreparedDocument],
        dict[str, DocumentRecord],
        dict[int, int],
    ]:
        self.import_tasks.set_status(
            task.task_id,
            "receiving",
            "正在接收并持久化附件。",
        )
        task_directory = self.import_tasks.task_directory(task)
        staging = task_directory / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        total_bytes = sum(item.size or 0 for item in task.files)
        seen_names: dict[str, tuple[str, int]] = {}
        duplicate_of: dict[int, int] = {}
        prepared: dict[int, PreparedDocument] = {}

        for item in task.files:
            if item.status == "pending":
                if sources is None or item.index >= len(sources):
                    self.import_tasks.update_file(
                        task.task_id,
                        item.index,
                        status="failed",
                        message=f"需要重新上传：{item.filename}",
                        error="服务重启前附件尚未完成暂存",
                    )
                    continue
                try:
                    values = prepare_sources(
                        [sources[item.index]],
                        self.settings,
                    )
                    if not values:
                        raise ValueError("附件内容为空")
                    document = values[0]
                    if len(document.data) > self.settings.max_file_bytes:
                        raise ValueError("单文件超过 50 MiB 限制")
                    total_bytes += len(document.data)
                    if total_bytes > self.settings.max_batch_bytes:
                        raise ValueError("批次总大小超过 500 MiB 限制")
                    relative_path = (
                        Path("staging")
                        / f"{item.index:03d}"
                        / document.filename
                    )
                    target = task_directory / relative_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(target.suffix + ".tmp")
                    temporary.write_bytes(document.data)
                    temporary.replace(target)
                    self.import_tasks.update_file(
                        task.task_id,
                        item.index,
                        status="staged",
                        message=(
                            f"第 {item.index + 1}/{len(task.files)} 份附件已暂存："
                            f"{document.filename}"
                        ),
                        filename=document.filename,
                        staged_relative_path=relative_path.as_posix(),
                        sha256=document.sha256,
                        size=len(document.data),
                        mime_type=document.mime_type,
                    )
                    item = self.import_tasks.get(task.task_id).files[item.index]
                except Exception as exc:
                    self.import_tasks.update_file(
                        task.task_id,
                        item.index,
                        status="failed",
                        message=f"附件接收失败：{item.filename}",
                        error=_safe_error(exc),
                    )
                    continue
            if item.status not in {"staged", "parsed", "archived"}:
                continue
            if not item.staged_relative_path:
                self.import_tasks.update_file(
                    task.task_id,
                    item.index,
                    status="failed",
                    message=f"暂存记录无效：{item.filename}",
                    error="缺少暂存路径",
                )
                continue
            path = task_directory / item.staged_relative_path
            if not path.is_file():
                self.import_tasks.update_file(
                    task.task_id,
                    item.index,
                    status="failed",
                    message=f"需要重新上传：{item.filename}",
                    error="暂存文件不存在",
                )
                continue
            data = path.read_bytes()
            digest = item.sha256 or hashlib.sha256(data).hexdigest()
            key = _filename_key(item.filename)
            previous = seen_names.get(key)
            if previous:
                if previous[0] == digest:
                    duplicate_of[item.index] = previous[1]
                    continue
                self.import_tasks.update_file(
                    task.task_id,
                    item.index,
                    status="failed",
                    message=f"同名冲突：{item.filename}",
                    error="同一批次中同名文件内容不同，按输入顺序保留第一份",
                )
                continue
            seen_names[key] = (digest, item.index)
            prepared[item.index] = PreparedDocument(
                filename=item.filename,
                data=data,
                sha256=digest,
                mime_type=item.mime_type or "",
                source_kind=item.source_kind,
            )

        self.import_tasks.set_status(
            task.task_id,
            "processing",
            f"正在校验并解析 {len(prepared)} 份候选文件。",
        )
        records: dict[str, DocumentRecord] = {}
        ocr_units = 0
        for index, document in list(prepared.items()):
            current = self.import_tasks.get(task.task_id).files[index]
            path = task_directory / (current.staged_relative_path or "")

            def report(stage: str, message: str) -> None:
                nonlocal ocr_units
                if stage == "ocr" and message.startswith("正在 OCR"):
                    ocr_units += 1
                    if ocr_units > self.settings.max_batch_ocr_pages:
                        raise ValueError("批次 OCR 页/图片数量超过限制")
                self.import_tasks.emit(task.task_id, stage, message)

            try:
                with document_progress(report):
                    record = self.manager.load_document_record(
                        path,
                        source_root=path.parent,
                    )
                if record is None:
                    raise ValueError("文档没有可检索内容")
                record.metadata["source"] = document.filename
                record.metadata["file_name"] = document.filename
                records[document.filename] = record
                self.import_tasks.update_file(
                    task.task_id,
                    index,
                    status="parsed",
                    message=f"解析完成：{document.filename}",
                )
                if self.object_store:
                    self.object_store.archive(
                        department=get_department(task.knowledge_id),
                        documents=[document],
                    )
                self.import_tasks.update_file(
                    task.task_id,
                    index,
                    status="archived",
                    message=f"原件归档完成：{document.filename}",
                )
            except Exception as exc:
                prepared.pop(index, None)
                records.pop(document.filename, None)
                self.import_tasks.update_file(
                    task.task_id,
                    index,
                    status="failed",
                    message=f"文件处理失败：{document.filename}",
                    error=_safe_error(exc),
                )
        return prepared, records, duplicate_of

    def import_status(
        self,
        department: Department,
        text: str,
    ) -> AgentResult:
        match = re.search(r"\b[0-9a-fA-F]{32}\b", text)
        task = (
            self.import_tasks.get(match.group(0).lower())
            if match
            else self.import_tasks.recent(department.knowledge_id)
        )
        if task is None or task.knowledge_id != department.knowledge_id:
            return self.result(
                department,
                Intent.IMPORT_STATUS,
                "当前知识空间没有可查询的导入任务。",
            )
        return self._task_result(department, task, intent=Intent.IMPORT_STATUS)

    def _task_result(
        self,
        department: Department,
        task: ImportTask,
        *,
        intent: Intent = Intent.SAVE,
    ) -> AgentResult:
        lines = [
            f"- {item.filename}：{item.status}"
            + (f"（{item.error}）" if item.error else "")
            for item in task.files
        ]
        return self.result(
            department,
            intent,
            (
                f"导入任务：{task.task_id}\n"
                f"状态：{task.status}\n"
                f"{task.message}\n\n"
                + "\n".join(lines)
            ),
            task_id=task.task_id,
            task_status=task.status,
        )

    def query(
        self,
        department: Department,
        question: str,
        *,
        top_k: int | None,
        has_attachments: bool,
        progress: ProgressCallback | None = None,
    ) -> AgentResult:
        source_documents: list[SourceDocument] = []
        try:
            rewritten: list[str] = []
            if self.settings.query_rewrite_enabled:
                if progress:
                    progress(
                        ProgressEvent("rewrite_query", "正在改写并拆分检索问题。")
                    )
                try:
                    rewritten = self.query_rewriter.rewrite(
                        question,
                        department=department.display_name,
                    )
                except QueryRewriteError:
                    if progress:
                        progress(
                            ProgressEvent(
                                "rewrite_query",
                                "查询改写不可用，已回退为原问题检索。",
                            )
                        )
            queries = merge_original_query(
                question,
                rewritten,
                limit=self.settings.max_rewritten_queries,
            )
            if progress:
                progress(
                    ProgressEvent(
                        "retrieve",
                        f"正在使用 {len(queries)} 个查询检索知识库。",
                    )
                )
            retrieval = self.manager.retrieve_many(
                department.knowledge_id,
                queries,
                top_k=top_k or self.settings.retrieval_top_k_per_query,
                max_chunks=self.settings.max_context_chunks,
                max_documents=self.settings.max_source_documents,
                rrf_k=self.settings.rrf_k,
            )
            if progress:
                progress(
                    ProgressEvent(
                        "answer",
                        f"已融合 {len(retrieval.citations)} 条证据，正在生成回答。",
                    )
                )
            answer = self.manager.answer_from_citations(
                question,
                retrieval.citations,
            )
        except FileNotFoundError:
            content = (
                f"“{department.display_name}”知识库尚未完成首次入库。"
                "请上传文件并明确说明“保存到知识库”。"
            )
        else:
            content = answer.answer
            source_documents = self._source_documents(
                department,
                answer.citations,
            )
            if source_documents:
                sources = "\n".join(f"- {item.filename}" for item in source_documents)
                content = f"{content}\n\n来源：\n{sources}"
        if has_attachments:
            content += (
                "\n\n提示：本次附件未保存；只有明确提出保存、入库或归档时才会写入知识库。"
            )
        return self.result(
            department,
            Intent.QUERY,
            content,
            source_documents=source_documents,
        )

    def _source_documents(
        self,
        department: Department,
        citations: list,
    ) -> list[SourceDocument]:
        manifest = self.manager.active_manifest(department.knowledge_id)
        catalog = manifest.get("document_catalog")
        if not isinstance(catalog, dict):
            catalog = {}
        fingerprints = manifest.get("documents")
        if not isinstance(fingerprints, dict):
            fingerprints = {}
        by_key = {
            _filename_key(filename): (filename, value)
            for filename, value in catalog.items()
            if isinstance(filename, str) and isinstance(value, dict)
        }
        results: list[SourceDocument] = []
        seen: set[str] = set()
        for citation in citations:
            basename = Path(str(citation.source).replace("\\", "/")).name
            key = _filename_key(basename)
            if not basename or key in seen:
                continue
            seen.add(key)
            catalog_name, metadata = by_key.get(key, (basename, {}))
            digest = metadata.get("sha256") or fingerprints.get(catalog_name)
            results.append(
                SourceDocument(
                    filename=Path(catalog_name).name,
                    sha256=digest if isinstance(digest, str) else None,
                )
            )
        return results

    def list_documents(self, department: Department) -> AgentResult:
        directory = self.manager.active_documents_dir(department.knowledge_id)
        files = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if files:
            lines = [
                f"- {path.relative_to(directory).as_posix()}（{path.stat().st_size} bytes）"
                for path in files
            ]
            content = (
                f"“{department.display_name}”知识库共有 {len(files)} 个文档：\n"
                + "\n".join(lines)
            )
        else:
            content = f"“{department.display_name}”知识库当前没有文档。"
        return self.result(department, Intent.LIST, content)

    def help(self, department: Department, intent: Intent = Intent.HELP) -> AgentResult:
        return self.result(
            department,
            intent,
            (
                f"当前知识空间：{department.display_name}（{department.knowledge_id}）。\n"
                "支持：基于本部门知识库问答；上传附件并明确说“保存/入库/归档”；"
                "查看本部门已保存文档和批量导入进度。知识库回答引用的来源文档会在"
                "“来源”下提供下载（一次最多 10 份）。\n"
                "不支持通过对话删除资料。"
            ),
        )

    def preview(
        self,
        department: Department,
        intent: Intent,
        *,
        source_count: int,
    ) -> AgentResult:
        actions = {
            Intent.SAVE: f"将保存并索引 {source_count} 个附件",
            Intent.QUERY: "将检索本部门知识库并生成有来源的回答",
            Intent.LIST: "将列出本部门已保存文档",
            Intent.IMPORT_STATUS: "将查询本部门最近或指定的导入任务",
            Intent.HELP: "将返回使用说明",
            Intent.UNKNOWN: "将要求用户澄清意图",
        }
        return self.result(
            department,
            intent,
            f"dry-run（未调用模型、未下载附件、未写入数据）：{actions[intent]}。",
        )

    @staticmethod
    def result(
        department: Department,
        intent: Intent,
        content: str,
        *,
        saved_documents: list | None = None,
        source_documents: list[SourceDocument] | None = None,
        task_id: str | None = None,
        task_status: str | None = None,
    ) -> AgentResult:
        return AgentResult(
            intent=intent,
            content=content,
            knowledge_id=department.knowledge_id,
            department=department.display_name,
            saved_documents=saved_documents or [],
            source_documents=source_documents or [],
            task_id=task_id,
            task_status=task_status,
        )


def build_graph(runtime: DepartmentKnowledgeBaseRuntime):
    def validate_scope(
        state: DepartmentKnowledgeBaseState,
    ) -> dict[str, Any]:
        department = get_department(state["knowledge_id"])
        if progress := state.get("progress"):
            progress(
                ProgressEvent(
                    "scope",
                    f"已锁定知识空间 {department.knowledge_id}。",
                )
            )
        return {"department": department}

    def recognize_intent(
        state: DepartmentKnowledgeBaseState,
    ) -> dict[str, Any]:
        if progress := state.get("progress"):
            progress(ProgressEvent("intent", "正在识别请求意图。"))
        if state.get("dry_run"):
            result = {
                "decision": recognize_intent_dry_run(
                    state.get("text", ""),
                    file_count=len(state.get("sources", [])),
                )
            }
        else:
            result = {
                "decision": runtime.intent_recognizer.recognize(
                    state.get("text", ""),
                    file_count=len(state.get("sources", [])),
                )
            }
        if progress := state.get("progress"):
            progress(
                ProgressEvent(
                    "intent",
                    f"已识别意图：{result['decision'].intent.value}。",
                )
            )
        return result

    def route(state: DepartmentKnowledgeBaseState) -> str:
        intent = state["decision"].intent
        if intent is Intent.SAVE:
            return "save"
        if intent is Intent.QUERY:
            return "query"
        if intent is Intent.LIST:
            return "list_documents"
        if intent is Intent.IMPORT_STATUS:
            return "import_status"
        if intent is Intent.HELP:
            return "help"
        return "unknown"

    def save(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.SAVE,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {
            "result": runtime.save(
                state["department"],
                state.get("sources", []),
                progress=state.get("progress"),
            )
        }

    def query(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.QUERY,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {
            "result": runtime.query(
                state["department"],
                state.get("text", ""),
                top_k=state.get("top_k"),
                has_attachments=bool(state.get("sources")),
                progress=state.get("progress"),
            )
        }

    def list_documents(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.LIST,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {"result": runtime.list_documents(state["department"])}

    def import_status(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.IMPORT_STATUS,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {
            "result": runtime.import_status(
                state["department"],
                state.get("text", ""),
            )
        }

    def help_node(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.HELP,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {"result": runtime.help(state["department"])}

    def unknown(state: DepartmentKnowledgeBaseState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "result": runtime.preview(
                    state["department"],
                    Intent.UNKNOWN,
                    source_count=len(state.get("sources", [])),
                )
            }
        return {
            "result": runtime.help(
                state["department"],
                Intent.UNKNOWN,
            )
        }

    graph = StateGraph(DepartmentKnowledgeBaseState)
    graph.add_node("validate_scope", validate_scope)
    graph.add_node("recognize_intent", recognize_intent)
    graph.add_node("save", save)
    graph.add_node("query", query)
    graph.add_node("list_documents", list_documents)
    graph.add_node("import_status", import_status)
    graph.add_node("help", help_node)
    graph.add_node("unknown", unknown)
    graph.add_edge(START, "validate_scope")
    graph.add_edge("validate_scope", "recognize_intent")
    graph.add_conditional_edges(
        "recognize_intent",
        route,
        {
            "save": "save",
            "query": "query",
            "list_documents": "list_documents",
            "import_status": "import_status",
            "help": "help",
            "unknown": "unknown",
        },
    )
    for node in (
        "save",
        "query",
        "list_documents",
        "import_status",
        "help",
        "unknown",
    ):
        graph.add_edge(node, END)
    return graph.compile()


def _safe_error(exc: Exception) -> str:
    """Return a bounded error message without retaining signed attachment URLs."""

    value = str(exc).strip() or exc.__class__.__name__
    value = re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[REDACTED]", value)
    return value[:500]


def get_department_ids() -> tuple[str, ...]:
    from .departments import DEPARTMENTS

    return tuple(DEPARTMENTS)


def _filename_key(value: str) -> str:
    return unicodedata.normalize(
        "NFC",
        Path(value.replace("\\", "/")).name,
    ).casefold()
