from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from src.agents.department_knowledge_base.import_tasks import (
    ImportTask,
    ImportTaskCoordinator,
    ImportTaskFile,
)
from src.agents.openai_compatible_inputs import AttachmentReference


def test_task_json_never_persists_presigned_url(tmp_path: Path) -> None:
    ran = threading.Event()
    coordinator = ImportTaskCoordinator(
        tmp_path,
        processor=lambda _task_id, _sources: ran.set(),
    )
    try:
        task = coordinator.create(
            "marketing",
            [
                AttachmentReference(
                    url=(
                        "https://files.example/uuid.pdf?"
                        "X-Amz-Signature=secret-value"
                    ),
                    filename="制度.pdf",
                    source_kind="file_url",
                )
            ],
        )
        assert ran.wait(2)
        task_json = (
            coordinator.task_directory(task) / "task.json"
        ).read_text(encoding="utf-8")
    finally:
        coordinator._executor.shutdown(wait=True)

    assert "制度.pdf" in task_json
    assert "files.example" not in task_json
    assert "X-Amz-Signature" not in task_json
    assert "secret-value" not in task_json


def test_recovery_submits_staged_task_without_expired_sources(tmp_path: Path) -> None:
    now = datetime.now(UTC).isoformat()
    task = ImportTask(
        task_id="d" * 32,
        knowledge_id="marketing",
        status="processing",
        files=[
            ImportTaskFile(
                index=0,
                filename="制度.txt",
                status="staged",
                staged_relative_path="staging/000/制度.txt",
                sha256="e" * 64,
                size=6,
            )
        ],
        created_at=now,
        updated_at=now,
    )
    task_dir = tmp_path / ".import_tasks" / "marketing" / task.task_id
    staged = task_dir / "staging" / "000" / "制度.txt"
    staged.parent.mkdir(parents=True)
    staged.write_text("制度内容", encoding="utf-8")
    (task_dir / "task.json").write_text(
        task.model_dump_json(indent=2),
        encoding="utf-8",
    )

    received: list[tuple[str, object]] = []
    ran = threading.Event()

    def processor(task_id, sources):
        received.append((task_id, sources))
        ran.set()

    coordinator = ImportTaskCoordinator(tmp_path, processor=processor)
    try:
        coordinator.recover()
        assert ran.wait(2)
    finally:
        coordinator._executor.shutdown(wait=True)

    assert received == [(task.task_id, None)]
