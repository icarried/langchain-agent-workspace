from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.batch_resume_review_llm.openai_compatible_api import (
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
                    "岗位要求：要求本科及以上学历，熟悉 Python。\n"
                    "简历文件：\n"
                    f"{resume_lines}"
                ),
            }
        ],
    }


def test_models_lists_batch_resume_review_agent() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    models = response.json()["data"]
    assert models[0]["id"] == MODEL_ID


def test_chat_completions_non_stream_dry_run(tmp_path: Path) -> None:
    resume = _write_resume(tmp_path / "candidate.txt", "姓名：张三\n本科\nPython\n")

    response = TestClient(app).post(
        "/v1/chat/completions",
        json=_chat_payload([resume], stream=False),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL_ID
    content = body["choices"][0]["message"]["content"]
    assert "# 批量简历审查与排序报告" in content
    assert "dry-run（未调用模型）" in content


def test_chat_completions_model_probe_without_review_input() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "batch-resume-review-agent 已就绪" in content
    assert "岗位要求" in content
    assert "简历文件" in content


def test_chat_completions_stream_model_probe_without_review_input() -> None:
    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "batch-resume-review-agent 已就绪" in text
    assert "data: [DONE]" in text


def test_extract_resume_paths_accepts_fastgpt_json_array() -> None:
    text = """
岗位要求：要求本科。
简历文件：
[
  "http://10.71.2.94:9000/fastgpt-private/chat/id/%E5%80%99%E9%80%89%E7%A4%BA%E4%BE%8B1.md?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=aaa&x-id=GetObject",
  "http://10.71.2.94:9000/fastgpt-private/chat/id/%E5%80%99%E9%80%89%E7%A4%BA%E4%BE%8B2.md?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=bbb&x-id=GetObject"
]
输出要求：请输出报告。
"""

    paths = _extract_resume_paths(text)

    assert len(paths) == 2
    assert paths[0].startswith("http://10.71.2.94:9000/fastgpt-private")
    assert paths[0].endswith("&x-id=GetObject")
    assert "X-Amz-Signature=bbb" in paths[1]


def test_chat_completions_stream_dry_run(tmp_path: Path) -> None:
    first = _write_resume(tmp_path / "first.txt", "姓名：张三\n本科\nPython\n")
    second = _write_resume(tmp_path / "second.txt", "姓名：李四\n本科\nJava\n")

    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json=_chat_payload([first, second], stream=True),
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "data: [DONE]" in text
    assert "已接收 2 份简历" in text
    assert "# 批量简历审查与排序报告" in text
    chunks = [
        line.removeprefix("data: ")
        for line in text.splitlines()
        if line.startswith("data: {")
    ]
    assert any(
        json.loads(chunk)["object"] == "chat.completion.chunk" for chunk in chunks
    )
