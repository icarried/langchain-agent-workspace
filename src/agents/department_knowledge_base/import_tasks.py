from __future__ import annotations

import queue
import shutil
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.agents.openai_compatible_inputs import AttachmentReference
from src.agents.remote_files import remote_filename

from .schemas import ProgressCallback, ProgressEvent


TaskStatus = Literal[
    "queued",
    "receiving",
    "processing",
    "publishing",
    "completed",
    "partial",
    "failed",
]
FileStatus = Literal[
    "pending",
    "staged",
    "parsed",
    "archived",
    "published",
    "failed",
]
TERMINAL_TASK_STATUSES = {"completed", "partial", "failed"}


class ImportTaskFile(BaseModel):
    index: int
    filename: str
    source_kind: str = "unknown"
    status: FileStatus = "pending"
    staged_relative_path: str | None = None
    sha256: str | None = None
    size: int | None = None
    mime_type: str | None = None
    error: str | None = None


class ImportTask(BaseModel):
    task_id: str
    knowledge_id: str
    status: TaskStatus = "queued"
    files: list[ImportTaskFile] = Field(default_factory=list)
    created_at: str
    updated_at: str
    revision: int = 0
    message: str = "任务已排队。"
    published_count: int = 0
    failed_count: int = 0
    final_version: str | None = None


TaskProcessor = Callable[
    [str, list[str | AttachmentReference] | None],
    None,
]


class ImportTaskCoordinator:
    def __init__(
        self,
        root: Path,
        *,
        processor: TaskProcessor,
        max_workers: int = 2,
        retention_days: int = 30,
    ) -> None:
        self.root = root / ".import_tasks"
        self.root.mkdir(parents=True, exist_ok=True)
        self.processor = processor
        self.retention_days = retention_days
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="department-kb-import",
        )
        self._lock = threading.RLock()
        self._sources: dict[str, list[str | AttachmentReference]] = {}
        self._events: dict[str, queue.Queue[ProgressEvent]] = {}
        self._submitted: set[str] = set()
        self._cleanup_expired()

    def recover(self) -> None:
        self._recover()

    def create(
        self,
        knowledge_id: str,
        sources: list[str | AttachmentReference],
    ) -> ImportTask:
        task_id = uuid.uuid4().hex
        now = _now()
        files = [
            ImportTaskFile(
                index=index,
                filename=_source_filename(source),
                source_kind=(
                    source.source_kind
                    if isinstance(source, AttachmentReference)
                    else "legacy"
                ),
            )
            for index, source in enumerate(sources)
        ]
        task = ImportTask(
            task_id=task_id,
            knowledge_id=knowledge_id,
            files=files,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._write(task)
            self._sources[task_id] = list(sources)
            self._events[task_id] = queue.Queue()
            self._submit(task_id)
        return task

    def get(self, task_id: str) -> ImportTask | None:
        path = self._find_task_path(task_id)
        if not path:
            return None
        try:
            return ImportTask.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def recent(self, knowledge_id: str) -> ImportTask | None:
        candidates: list[ImportTask] = []
        directory = self.root / knowledge_id
        if not directory.exists():
            return None
        for path in directory.glob("*/task.json"):
            try:
                candidates.append(
                    ImportTask.model_validate_json(path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError):
                continue
        return max(candidates, key=lambda item: item.created_at) if candidates else None

    def stats(self) -> dict[str, int]:
        queued = 0
        active = 0
        for path in self.root.glob("*/*/task.json"):
            try:
                status = ImportTask.model_validate_json(
                    path.read_text(encoding="utf-8")
                ).status
            except (OSError, ValueError):
                continue
            if status == "queued":
                queued += 1
            elif status not in TERMINAL_TASK_STATUSES:
                active += 1
        return {"queued_tasks": queued, "active_tasks": active}

    def wait(
        self,
        task_id: str,
        *,
        progress: ProgressCallback | None,
    ) -> ImportTask:
        event_queue = self._events.setdefault(task_id, queue.Queue())
        while True:
            task = self.get(task_id)
            if task is None:
                raise ValueError(f"import task not found: {task_id}")
            if task.status in TERMINAL_TASK_STATUSES:
                return task
            try:
                event = event_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if progress:
                progress(event)

    def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
        *,
        final_version: str | None = None,
    ) -> ImportTask:
        def mutate(task: ImportTask) -> None:
            task.status = status
            task.message = message
            if final_version is not None:
                task.final_version = final_version

        task = self.update(task_id, mutate)
        self.emit(task_id, status, message)
        if status in TERMINAL_TASK_STATUSES:
            self._cleanup_staging(task)
        return task

    def update_file(
        self,
        task_id: str,
        index: int,
        *,
        status: FileStatus,
        message: str,
        filename: str | None = None,
        staged_relative_path: str | None = None,
        sha256: str | None = None,
        size: int | None = None,
        mime_type: str | None = None,
        error: str | None = None,
    ) -> ImportTask:
        def mutate(task: ImportTask) -> None:
            item = task.files[index]
            item.status = status
            if filename is not None:
                item.filename = filename
            if staged_relative_path is not None:
                item.staged_relative_path = staged_relative_path
            if sha256 is not None:
                item.sha256 = sha256
            if size is not None:
                item.size = size
            if mime_type is not None:
                item.mime_type = mime_type
            if error is not None:
                item.error = error[:1000]
            task.message = message
            task.published_count = sum(
                file.status == "published" for file in task.files
            )
            task.failed_count = sum(file.status == "failed" for file in task.files)

        task = self.update(task_id, mutate)
        self.emit(task_id, status, message)
        return task

    def update(
        self,
        task_id: str,
        mutator: Callable[[ImportTask], None],
    ) -> ImportTask:
        with self._lock:
            task = self.get(task_id)
            if task is None:
                raise ValueError(f"import task not found: {task_id}")
            mutator(task)
            task.revision += 1
            task.updated_at = _now()
            self._write(task)
            return task

    def task_directory(self, task: ImportTask) -> Path:
        return self.root / task.knowledge_id / task.task_id

    def emit(self, task_id: str, stage: str, message: str) -> None:
        self._events.setdefault(task_id, queue.Queue()).put(
            ProgressEvent(stage, message)
        )

    def _submit(self, task_id: str) -> None:
        if task_id in self._submitted:
            return
        self._submitted.add(task_id)
        self._executor.submit(self._run, task_id)

    def _run(self, task_id: str) -> None:
        try:
            self.processor(task_id, self._sources.pop(task_id, None))
        finally:
            with self._lock:
                self._submitted.discard(task_id)

    def _recover(self) -> None:
        for path in self.root.glob("*/*/task.json"):
            try:
                task = ImportTask.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if task.status not in TERMINAL_TASK_STATUSES:
                self._events.setdefault(task.task_id, queue.Queue())
                self._submit(task.task_id)

    def _cleanup_expired(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        for path in self.root.glob("*/*/task.json"):
            try:
                task = ImportTask.model_validate_json(path.read_text(encoding="utf-8"))
                updated = datetime.fromisoformat(task.updated_at)
            except (OSError, ValueError):
                continue
            if task.status in TERMINAL_TASK_STATUSES and updated < cutoff:
                shutil.rmtree(path.parent, ignore_errors=True)

    def _cleanup_staging(self, task: ImportTask) -> None:
        staging = self.task_directory(task) / "staging"
        shutil.rmtree(staging, ignore_errors=True)

    def _find_task_path(self, task_id: str) -> Path | None:
        matches = list(self.root.glob(f"*/{task_id}/task.json"))
        return matches[0] if matches else None

    def _write(self, task: ImportTask) -> None:
        path = self.root / task.knowledge_id / task.task_id / "task.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            task.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)


def _source_filename(source: str | AttachmentReference) -> str:
    if isinstance(source, AttachmentReference):
        value = source.filename or remote_filename(source.url)
    else:
        value = remote_filename(source)
    return Path(value.replace("\\", "/")).name or "document"


def _now() -> str:
    return datetime.now(UTC).isoformat()
