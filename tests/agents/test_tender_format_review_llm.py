from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.agents.tender_format_review.openai_compatible_api import (
    ChatCompletionRequest,
    MODEL_ID,
    _extract_docx_inputs,
    _temporary_minio_transport_mapping,
    app,
    parse_review_request,
)


def _chat_payload(*, stream: bool) -> dict[str, object]:
    return {
        "model": MODEL_ID,
        "stream": stream,
        "dry_run": True,
        "messages": [
            {
                "role": "user",
                "content": (
                    "招标文件：\n"
                    "./临时文件/仅包含一行文字的文件.docx\n\n"
                    "输出要求：请输出招标文件格式审查报告。"
                ),
            }
        ],
    }


def test_models_lists_tender_format_review_agent() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    models = response.json()["data"]
    assert models[0]["id"] == MODEL_ID


def test_chat_completions_non_stream_dry_run() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json=_chat_payload(stream=False),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL_ID
    content = body["choices"][0]["message"]["content"]
    assert "dry-run 报告" in content


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
    assert "tender-format-review-agent 已就绪" in content
    assert "招标文件" in content


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

    assert "tender-format-review-agent 已就绪" in text
    assert "reasoning_content" in text
    assert "data: [DONE]" in text


def test_chat_completions_stream_can_disable_thinking() -> None:
    payload = _chat_payload(stream=True)
    payload["thinking"] = False

    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json=payload,
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "已接收 1 份招标文件" in text
    assert "reasoning_content" not in text
    assert '"content"' in text


def test_extract_docx_inputs_accepts_fastgpt_json_array() -> None:
    text = """
招标文件：
[
  "http://10.71.2.94:9000/fastgpt-private/chat/id/%E6%8B%9B%E6%A0%87.docx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=aaa&x-id=GetObject"
]
输出要求：请输出报告。
"""

    paths = _extract_docx_inputs(text)

    assert len(paths) == 1
    assert paths[0].startswith("http://10.71.2.94:9000/fastgpt-private")
    assert paths[0].endswith("&x-id=GetObject")


def test_extract_docx_inputs_accepts_attachment_block() -> None:
    text = """
附件：
- 待审招标文件.docx: http://minio.example/tender.docx?X-Amz-Signature=aaa

输出要求：请输出报告。
"""

    paths = _extract_docx_inputs(text)

    assert paths == ["http://minio.example/tender.docx?X-Amz-Signature=aaa"]


def test_parse_review_request_accepts_file_url_content_part() -> None:
    request = ChatCompletionRequest(
        model=MODEL_ID,
        dry_run=True,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请审查这份招标文件。"},
                    {
                        "type": "file_url",
                        "file_url": {"url": "http://minio.example/tender.docx"},
                    },
                ],
            }
        ],
    )

    parsed = parse_review_request(request)

    assert parsed is not None
    assert parsed.docx_input == "http://minio.example/tender.docx"


def test_remote_docx_request_uses_configured_transport_override(monkeypatch) -> None:
    monkeypatch.setenv(
        "AGENT_FILE_TRANSPORT_OVERRIDES",
        '{"10.71.2.94:9000":"http://127.0.0.1:9002"}',
    )
    url, headers = _temporary_minio_transport_mapping(
        "http://10.71.2.94:9000/fastgpt-private/chat/id/%E6%8B%9B%E6%A0%87.docx"
        "?X-Amz-Signature=aaa&x-id=GetObject"
    )

    assert url.startswith("http://127.0.0.1:9002/fastgpt-private")
    assert url.endswith("?X-Amz-Signature=aaa&x-id=GetObject")
    assert headers["Host"] == "10.71.2.94:9000"


def test_chat_completions_stream_dry_run() -> None:
    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json=_chat_payload(stream=True),
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "data: [DONE]" in text
    assert "已接收 1 份招标文件" in text
    assert "reasoning_content" in text
    assert "dry-run 报告" in text
    chunks = [
        line.removeprefix("data: ")
        for line in text.splitlines()
        if line.startswith("data: {")
    ]
    assert any(
        json.loads(chunk)["object"] == "chat.completion.chunk" for chunk in chunks
    )
    assert any(
        "dry-run 报告" in json.loads(chunk)["choices"][0]["delta"].get("content", "")
        for chunk in chunks
    )
