from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.smart_resume_screening.openai_compatible_api import (
    MODEL_ID,
    _extract_resume_paths,
    app,
)


def _write_resume(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _chat_payload(resumes: list[Path], *, stream: bool) -> dict[str, object]:
    resume_lines = "\n".join(str(path) for path in resumes)
    return {
        "model": MODEL_ID,
        "stream": stream,
        "dry_run": True,
        "messages": [
            {
                "role": "user",
                "content": (
                    "岗位要求：\n"
                    "职位名称：AI 应用开发工程师\n"
                    "硬性条件：本科，计算机，Python\n"
                    "优先条件：FastAPI，上线\n\n"
                    "简历文件：\n"
                    f"{resume_lines}\n\n"
                    "输出要求：请输出智能简历筛选报告。"
                ),
            }
        ],
    }


def test_models_lists_smart_resume_screening_agent() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == MODEL_ID


def test_chat_completions_model_probe_without_screening_input() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hello"}], "stream": False},
    )

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "smart-resume-screening-agent 已就绪" in content
    assert "岗位要求" in content
    assert "简历文件" in content


def test_chat_completions_non_stream_dry_run(tmp_path: Path) -> None:
    resume = _write_resume(tmp_path / "candidate.txt", "姓名：李明\n本科\n计算机\nPython\nFastAPI\n")

    response = TestClient(app).post("/v1/chat/completions", json=_chat_payload([resume], stream=False))

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL_ID
    content = body["choices"][0]["message"]["content"]
    assert "智能简历筛选 dry-run 报告" in content
    assert "李明" in content


def test_chat_completions_stream_dry_run(tmp_path: Path) -> None:
    first = _write_resume(tmp_path / "first.txt", "姓名：李明\n本科\n计算机\nPython\nFastAPI\n")
    second = _write_resume(tmp_path / "second.txt", "姓名：王芳\n本科\n传媒\n")

    with TestClient(app).stream("POST", "/v1/chat/completions", json=_chat_payload([first, second], stream=True)) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "data: [DONE]" in text
    assert "已接收 2 份简历" in text
    assert "reasoning_content" in text
    assert "智能简历筛选 dry-run 报告" in text
    chunks = [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: {")]
    assert any(json.loads(chunk)["object"] == "chat.completion.chunk" for chunk in chunks)


def test_chat_completions_stream_can_disable_thinking(tmp_path: Path) -> None:
    resume = _write_resume(tmp_path / "candidate.txt", "姓名：李明\n本科\n计算机\nPython\n")
    payload = _chat_payload([resume], stream=True)
    payload["thinking"] = False

    with TestClient(app).stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "已接收 1 份简历" in text
    assert "reasoning_content" not in text
    assert '"content"' in text


def test_extract_resume_paths_accepts_fastgpt_json_array() -> None:
    text = """
岗位要求：本科，Python
简历文件：
[
  "http://minio.example/candidate-a.pdf?X-Amz-Signature=aaa",
  "http://minio.example/candidate-b.docx?X-Amz-Signature=bbb"
]
输出要求：请输出报告。
"""

    paths = _extract_resume_paths(text)

    assert len(paths) == 2
    assert paths[0].endswith("X-Amz-Signature=aaa")
    assert paths[1].endswith("X-Amz-Signature=bbb")
