from __future__ import annotations

import threading
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.openai_compatible_inputs import AttachmentReference
from src.document_ocr import GPUStackPaddleOCRVL, OCRProvider
from src.knowledge_base.manager import KnowledgeBaseManager
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
from .object_store import DepartmentObjectStore, MinioDepartmentObjectStore
from .schemas import (
    AgentResult,
    Intent,
    IntentDecision,
    ProgressCallback,
    ProgressEvent,
)
from .settings import DepartmentKnowledgeBaseSettings
from .storage import describe_documents, prepare_sources


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
        ocr_provider: OCRProvider | None = None,
        object_store: DepartmentObjectStore | None = None,
    ) -> None:
        self.settings = settings or DepartmentKnowledgeBaseSettings()
        self._manager = manager
        self._intent_recognizer = intent_recognizer
        self._ocr_provider = ocr_provider
        self._object_store = object_store
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
        prepared = prepare_sources(sources, self.settings, progress=progress)
        if progress:
            progress(
                ProgressEvent(
                    "wait_for_lock",
                    f"正在等待知识空间 {department.knowledge_id} 的写入锁。",
                )
            )
        with self._locks[department.knowledge_id]:
            if progress:
                progress(
                    ProgressEvent(
                        "write_lock",
                        f"已获得知识空间 {department.knowledge_id} 的写入锁。",
                    )
                )
            object_store = self.object_store
            locations = []
            if object_store:
                for index, document in enumerate(prepared, start=1):
                    if progress:
                        progress(
                            ProgressEvent(
                                "archive",
                                f"正在归档第 {index}/{len(prepared)} 个原件："
                                f"{document.filename}",
                            )
                        )
                    locations.extend(object_store.archive(department, [document]))
                    if progress:
                        progress(
                            ProgressEvent(
                                "archive",
                                f"第 {index}/{len(prepared)} 个原件已归档："
                                f"{document.filename}",
                            )
                        )
            saved = describe_documents(
                self.manager.active_documents_dir(department.knowledge_id),
                prepared,
            )
            if locations:
                saved = [
                    item.model_copy(
                        update={
                            "object_bucket": location.bucket,
                            "object_key": location.object_key,
                        }
                    )
                    for item, location in zip(saved, locations, strict=True)
                ]
            with document_progress(
                (
                    lambda stage, message: progress(ProgressEvent(stage, message))
                    if progress
                    else None
                )
            ):
                ingestion = self.manager.publish_document_updates(
                    department.knowledge_id,
                    {item.filename: item.data for item in prepared},
                    progress=(
                        lambda stage, message: progress(ProgressEvent(stage, message))
                        if progress
                        else None
                    ),
                )
            if progress:
                progress(
                    ProgressEvent(
                        "commit",
                        (
                            "文档内容未变化，当前索引保持不变。"
                            if ingestion.unchanged
                            else "新文档快照、manifest 和 Chroma 索引已原子发布。"
                        ),
                    )
                )
        lines = [
            f"- {item.filename}（{item.size_bytes} bytes"
            f"{'，内容已存在' if item.unchanged else ''}）"
            for item in saved
        ]
        return self.result(
            department,
            Intent.SAVE,
            (
                f"已保存到“{department.display_name}”知识库并完成索引。\n\n"
                + "\n".join(lines)
                + f"\n\n本次写入 {ingestion.chunks_written} 个检索分块。"
            ),
            saved_documents=saved,
        )

    def query(
        self,
        department: Department,
        question: str,
        *,
        top_k: int | None,
        has_attachments: bool,
    ) -> AgentResult:
        try:
            answer = self.manager.answer(
                department.knowledge_id,
                question,
                top_k=top_k,
            )
        except FileNotFoundError:
            content = (
                f"“{department.display_name}”知识库尚未完成首次入库。"
                "请上传文件并明确说明“保存到知识库”。"
            )
        else:
            content = answer.answer
            if answer.citations:
                sources = "\n".join(
                    f"- {item.source}#chunk-{item.chunk_index}"
                    for item in answer.citations
                )
                content = f"{content}\n\n来源：\n{sources}"
        if has_attachments:
            content += (
                "\n\n提示：本次附件未保存；只有明确提出保存、入库或归档时才会写入知识库。"
            )
        return self.result(department, Intent.QUERY, content)

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
                "查看本部门已保存文档。\n"
                "不支持通过对话删除资料、切换部门或访问其他部门知识库。"
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
    ) -> AgentResult:
        return AgentResult(
            intent=intent,
            content=content,
            knowledge_id=department.knowledge_id,
            department=department.display_name,
            saved_documents=saved_documents or [],
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
            "help": "help",
            "unknown": "unknown",
        },
    )
    for node in ("save", "query", "list_documents", "help", "unknown"):
        graph.add_edge(node, END)
    return graph.compile()


def get_department_ids() -> tuple[str, ...]:
    from .departments import DEPARTMENTS

    return tuple(DEPARTMENTS)
