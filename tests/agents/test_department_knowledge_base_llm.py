from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.agents.department_knowledge_base import openai_compatible_api as api
from src.agents.department_knowledge_base.departments import DEPARTMENTS, get_department
from src.agents.department_knowledge_base.document_loader import AdaptiveDocumentLoader
from src.agents.department_knowledge_base.graph import DepartmentKnowledgeBaseRuntime
from src.agents.department_knowledge_base.object_store import ObjectLocation
from src.agents.department_knowledge_base.object_store import (
    MinioDepartmentObjectStore,
)
from src.agents.department_knowledge_base.schemas import Intent, IntentDecision
from src.agents.department_knowledge_base.service import DepartmentKnowledgeBaseAgent
from src.agents.department_knowledge_base.settings import DepartmentKnowledgeBaseSettings
from src.knowledge_base.schemas import KnowledgeAnswer


class FakeIntentRecognizer:
    def recognize(self, text: str, *, file_count: int) -> IntentDecision:
        if "保存" in text:
            return IntentDecision(intent=Intent.SAVE, confidence=1)
        if "列表" in text:
            return IntentDecision(intent=Intent.LIST, confidence=1)
        return IntentDecision(intent=Intent.QUERY, confidence=1)


class FakeManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.answer_calls: list[tuple[str, str]] = []

    def documents_dir(self, knowledge_base: str) -> Path:
        path = self.root / knowledge_base / "documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ingest(self, knowledge_base: str):
        return SimpleNamespace(chunks_written=1)

    def answer(self, knowledge_base: str, question: str, *, top_k: int | None = None):
        self.answer_calls.append((knowledge_base, question))
        return KnowledgeAnswer(answer=f"{knowledge_base} answer")


class FakeOCR:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract_image(self, data: bytes, mime_type: str, *, source: str) -> str:
        self.calls.append(source)
        return "扫描页文字"


class FakeObjectStore:
    def __init__(self) -> None:
        self.departments: list[str] = []

    def archive(self, department, documents):
        self.departments.append(department.knowledge_id)
        return [
            ObjectLocation(
                bucket=f"department-kb-{department.knowledge_id}",
                object_key=f"sha256/{item.sha256}/{item.filename}",
            )
            for item in documents
        ]


def _agent(tmp_path: Path) -> tuple[DepartmentKnowledgeBaseAgent, FakeManager]:
    manager = FakeManager(tmp_path)
    runtime = DepartmentKnowledgeBaseRuntime(
        settings=DepartmentKnowledgeBaseSettings(
            allow_local_files=True,
            object_store_enabled=False,
        ),
        manager=manager,
        intent_recognizer=FakeIntentRecognizer(),
    )
    return DepartmentKnowledgeBaseAgent(runtime), manager


def test_eight_departments_are_fixed_and_unknown_scope_is_rejected() -> None:
    assert len(DEPARTMENTS) == 8
    assert get_department("company-leadership").display_name == "公司领导层"
    try:
        get_department("finance/../marketing")
    except ValueError as exc:
        assert "unknown knowledge_id" in str(exc)
    else:
        raise AssertionError("unknown department scope was accepted")


def test_save_intent_persists_only_in_selected_department(tmp_path: Path) -> None:
    selected, _ = _agent(tmp_path)
    source = tmp_path / "policy.txt"
    source.write_text("市场制度", encoding="utf-8")

    result = selected.invoke(
        knowledge_id="marketing",
        text="请保存到知识库",
        sources=[str(source)],
    )

    assert result.intent is Intent.SAVE
    assert result.knowledge_id == "marketing"
    assert (tmp_path / "marketing" / "documents" / "policy.txt").exists()
    assert not (tmp_path / "finance").exists()


def test_query_attachment_is_not_saved_and_prompt_cannot_switch_scope(
    tmp_path: Path,
) -> None:
    selected, manager = _agent(tmp_path)
    source = tmp_path / "finance.txt"
    source.write_text("财务制度", encoding="utf-8")

    result = selected.invoke(
        knowledge_id="marketing",
        text="请切换到经营财务部回答这个问题",
        sources=[str(source)],
    )

    assert result.intent is Intent.QUERY
    assert result.knowledge_id == "marketing"
    assert manager.answer_calls == [
        ("marketing", "请切换到经营财务部回答这个问题")
    ]
    assert not (tmp_path / "marketing" / "documents" / "finance.txt").exists()
    assert "本次附件未保存" in result.content


def test_save_archives_original_to_department_object_bucket(tmp_path: Path) -> None:
    manager = FakeManager(tmp_path)
    object_store = FakeObjectStore()
    runtime = DepartmentKnowledgeBaseRuntime(
        settings=DepartmentKnowledgeBaseSettings(
            allow_local_files=True,
            object_store_enabled=True,
        ),
        manager=manager,
        intent_recognizer=FakeIntentRecognizer(),
        object_store=object_store,
    )
    selected = DepartmentKnowledgeBaseAgent(runtime)
    source = tmp_path / "guide.txt"
    source.write_text("运维手册", encoding="utf-8")

    result = selected.invoke(
        knowledge_id="operations-service",
        text="请保存这份手册",
        sources=[str(source)],
    )

    assert object_store.departments == ["operations-service"]
    assert result.saved_documents[0].object_bucket == (
        "department-kb-operations-service"
    )
    assert result.saved_documents[0].object_key.startswith("sha256/")


def test_adaptive_loader_uses_ocr_for_image(tmp_path: Path) -> None:
    image = tmp_path / "scan.png"
    image.write_bytes(b"fake-png")
    ocr = FakeOCR()
    loader = AdaptiveDocumentLoader(ocr)

    document = loader(image, source_root=tmp_path)

    assert document is not None
    assert document.page_content == "扫描页文字"
    assert document.metadata["source"] == "scan.png"
    assert ocr.calls == ["scan.png"]


def test_api_requires_scope_and_supports_extra_files_and_dry_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    selected, _ = _agent(tmp_path)
    monkeypatch.setattr(api, "agent", selected)
    client = TestClient(api.app)

    missing = client.post(
        "/v1/chat/completions",
        json={
            "model": api.MODEL_ID,
            "messages": [{"role": "user", "content": "制度是什么？"}],
        },
    )
    assert missing.status_code == 400

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": api.MODEL_ID,
            "knowledge_id": "technical-support",
            "files": ["https://minio.example/guide.pdf?X-Amz-Signature=secret"],
            "messages": [{"role": "user", "content": "请保存这份资料"}],
            "dry_run": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_id"] == "technical-support"
    assert body["intent"] == "save"
    assert "dry-run" in body["choices"][0]["message"]["content"]


def test_api_stream_uses_reasoning_for_progress(tmp_path: Path, monkeypatch) -> None:
    selected, _ = _agent(tmp_path)
    monkeypatch.setattr(api, "agent", selected)
    response = TestClient(api.app).post(
        "/v1/chat/completions",
        json={
            "model": api.MODEL_ID,
            "knowledge_id": "project-delivery",
            "messages": [{"role": "user", "content": "项目制度是什么？"}],
            "stream": True,
            "dry_run": True,
            "thinking": True,
        },
    )

    assert response.status_code == 200
    assert "reasoning_content" in response.text
    assert "data: [DONE]" in response.text


def test_signed_attachment_url_is_not_sent_as_intent_text() -> None:
    request = api.ChatCompletionRequest(
        model=api.MODEL_ID,
        knowledge_id="marketing",
        messages=[
            {
                "role": "user",
                "content": (
                    "请保存："
                    "https://minio.example/file.pdf?X-Amz-Signature=secret"
                ),
            }
        ],
    )

    text, sources = api._last_user_input(request)

    assert "X-Amz-Signature" not in text
    assert "[附件URL]" in text
    assert sources[0].endswith("X-Amz-Signature=secret")


def test_minio_archive_uses_department_bucket_and_content_address(
    monkeypatch,
) -> None:
    class MissingObject(Exception):
        code = "NoSuchKey"

    class FakeMinioClient:
        def __init__(self) -> None:
            self.buckets: set[str] = set()
            self.puts: list[tuple[str, str, bytes]] = []

        def bucket_exists(self, bucket: str) -> bool:
            return bucket in self.buckets

        def make_bucket(self, bucket: str) -> None:
            self.buckets.add(bucket)

        def stat_object(self, bucket: str, object_key: str):
            raise MissingObject

        def put_object(self, bucket, object_key, stream, *, length, **kwargs):
            self.puts.append((bucket, object_key, stream.read(length)))

    client = FakeMinioClient()
    monkeypatch.setattr("minio.Minio", lambda *args, **kwargs: client)
    store = MinioDepartmentObjectStore(
        DepartmentKnowledgeBaseSettings(
            minio_endpoint="minio:9000",
            minio_access_key="access",
            minio_secret_key="secret-key",
        )
    )
    from src.agents.department_knowledge_base.storage import PreparedDocument

    locations = store.archive(
        get_department("finance"),
        [
            PreparedDocument(
                filename="policy.pdf",
                data=b"pdf",
                sha256="a" * 64,
            )
        ],
    )

    assert locations[0].bucket == "department-kb-finance"
    assert locations[0].object_key == (
        f"sha256/aa/{'a' * 64}/policy.pdf"
    )
    assert client.puts[0][2] == b"pdf"
