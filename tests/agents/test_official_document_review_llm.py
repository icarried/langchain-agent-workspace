from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.official_document_review.openai_compatible_api import MODEL_ID, app


def _write_document(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _payload(document: Path, *, stream: bool) -> dict[str, object]:
    return {
        "model": MODEL_ID,
        "stream": stream,
        "dry_run": True,
        "messages": [
            {
                "role": "user",
                "content": (
                    "公文类型：通知\n\n"
                    "公文文件：\n"
                    f"{document}\n\n"
                    "输出要求：请输出公文格式检查报告。"
                ),
            }
        ],
    }


def test_models_lists_official_document_review_agent() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == MODEL_ID


def test_chat_completions_model_probe_without_input() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hello"}], "stream": False},
    )

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "official-document-review-agent 已就绪" in content
    assert "公文文件" in content


def test_chat_completions_non_stream_dry_run(tmp_path: Path) -> None:
    document = _write_document(tmp_path / "notice.txt", "关于开展测试工作的通知\n各部门：\n请落实。\n")

    response = TestClient(app).post("/v1/chat/completions", json=_payload(document, stream=False))

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "公文格式检查 dry-run 报告" in content
    assert "通知" in content


def test_chat_completions_stream_dry_run(tmp_path: Path) -> None:
    document = _write_document(tmp_path / "notice.txt", "关于开展测试工作的通知\n各部门：\n请落实。\n")

    with TestClient(app).stream("POST", "/v1/chat/completions", json=_payload(document, stream=True)) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "data: [DONE]" in text
    assert "已接收 1 份公文" in text
    assert "reasoning_content" in text
    assert "公文格式检查 dry-run 报告" in text
    chunks = [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: {")]
    assert any(json.loads(chunk)["object"] == "chat.completion.chunk" for chunk in chunks)


def test_chat_completions_stream_can_disable_thinking(tmp_path: Path) -> None:
    document = _write_document(tmp_path / "notice.txt", "关于开展测试工作的通知\n各部门：\n请落实。\n")
    payload = _payload(document, stream=True)
    payload["thinking"] = False

    with TestClient(app).stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "已接收 1 份公文" in text
    assert "reasoning_content" not in text
    assert '"content"' in text
