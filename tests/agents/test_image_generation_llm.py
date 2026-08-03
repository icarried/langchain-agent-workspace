from __future__ import annotations

import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.agents.image_generation.client import (
    GPUStackClient,
    extract_image_reference,
    parse_rewritten_prompt,
)
from src.agents.image_generation.graph import DRY_RUN_IMAGE
from src.agents.image_generation.inputs import (
    normalize_extracted_source,
    parse_conversation,
)
from src.agents.image_generation.openai_compatible_api import MODEL_ID, app
from src.agents.image_generation.service import generate_image
from src.agents.image_generation.settings import ImageGenerationSettings


PNG_BYTES = base64.b64decode(DRY_RUN_IMAGE.split(",", 1)[1])


def test_default_generation_and_edit_models() -> None:
    settings = ImageGenerationSettings()
    assert settings.image_generation_model == "z-image-turbo"
    assert settings.image_edit_model == "qwen-image-edit"


def _image_part(url: str) -> dict:
    return {"type": "image_url", "image_url": {"url": url}}


def test_parse_conversation_routes_text_to_generation() -> None:
    parsed = parse_conversation([{"role": "user", "content": "画一只猫"}])
    assert parsed.instruction == "画一只猫"
    assert parsed.image_source is None


def test_current_user_image_overrides_previous_assistant_image() -> None:
    parsed = parse_conversation(
        [
            {
                "role": "assistant",
                "content": [_image_part("data:image/png;base64,old")],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "改成蓝色"},
                    _image_part("data:image/png;base64,new"),
                ],
            },
        ]
    )
    assert parsed.image_source == "data:image/png;base64,new"
    assert parsed.image_from_current_user is True


def test_latest_assistant_image_is_reused_for_editing() -> None:
    parsed = parse_conversation(
        [
            {"role": "assistant", "content": [_image_part(DRY_RUN_IMAGE)]},
            {"role": "user", "content": "再亮一点"},
        ]
    )
    assert parsed.image_source == DRY_RUN_IMAGE
    assert parsed.image_from_current_user is False


def test_multiple_current_images_are_rejected() -> None:
    with pytest.raises(ValueError, match="只支持一张"):
        parse_conversation(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "合成"},
                        _image_part(DRY_RUN_IMAGE),
                        _image_part(DRY_RUN_IMAGE + "x"),
                    ],
                }
            ]
        )


def test_raw_base64_image_is_normalized() -> None:
    source = f"raw-base64:image/png:{base64.b64encode(PNG_BYTES).decode()}"
    assert normalize_extracted_source(source, max_bytes=1024).startswith(
        "data:image/png;base64,"
    )


def test_invalid_base64_is_rejected() -> None:
    with pytest.raises(ValueError, match="Base64"):
        normalize_extracted_source(
            "raw-base64:image/png:not_base64!",
            max_bytes=1024,
        )


def test_remote_image_is_downloaded_and_normalized(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.agents.image_generation.inputs.read_remote_file",
        lambda _url, max_bytes: (PNG_BYTES, "image/png"),
    )
    result = normalize_extracted_source("https://files.example/a.png", max_bytes=1024)
    assert result.startswith("data:image/png;base64,")


def test_dry_run_graph_routes_generation_and_editing() -> None:
    generated = generate_image(
        [{"role": "user", "content": "画一只猫"}],
        dry_run=True,
    )
    edited = generate_image(
        [
            {"role": "assistant", "content": [_image_part(DRY_RUN_IMAGE)]},
            {"role": "user", "content": "改成蓝色"},
        ],
        dry_run=True,
    )
    assert generated.mode == "generate"
    assert edited.mode == "edit"
    assert edited.image_url == DRY_RUN_IMAGE


def test_gpu_stack_client_sends_image_to_rewriter_and_routes_edit(monkeypatch) -> None:
    monkeypatch.setenv("GPU_STACK_API_KEY", "test-key")
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload)
        if payload["model"] == "qwen3.6-35b-a3b":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"rewritten_prompt":"把猫改成蓝色，其他区域保持不变"}'
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "done"},
                                _image_part(DRY_RUN_IMAGE),
                            ]
                        }
                    }
                ]
            },
        )

    client = GPUStackClient(
        ImageGenerationSettings(),
        transport=httpx.MockTransport(handler),
    )
    result = generate_image(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "改成蓝色"},
                    _image_part(DRY_RUN_IMAGE),
                ],
            }
        ],
        client=client,
    )
    assert result.mode == "edit"
    assert result.image_url == DRY_RUN_IMAGE
    assert captured[0]["model"] == "qwen3.6-35b-a3b"
    assert captured[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured[0]["messages"][1]["content"][1]["type"] == "image_url"
    assert captured[1]["model"] == "qwen-image-edit"


def test_response_parsers_accept_json_markdown_url_and_b64() -> None:
    assert parse_rewritten_prompt('```json\n{"rewritten_prompt":"a cat"}\n```') == "a cat"
    markdown_payload = {
        "choices": [{"message": {"content": "![result](https://img.example/a.png)"}}]
    }
    b64_payload = {
        "choices": [
            {
                "message": {
                    "content": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}]
                }
            }
        ]
    }
    assert extract_image_reference(markdown_payload, max_bytes=4096).startswith("https://")
    assert extract_image_reference(b64_payload, max_bytes=4096).startswith(
        "data:image/png;base64,"
    )


def test_openai_non_stream_dry_run_returns_multimodal_content() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "画一只猫"}],
            "stream": False,
            "dry_run": True,
        },
    )
    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"


def test_openai_stream_dry_run_returns_image_content_array() -> None:
    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "画一只猫"}],
            "stream": True,
            "dry_run": True,
        },
    ) as response:
        response.read()
        text = response.text
    chunks = [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: {")
    ]
    contents = [
        chunk["choices"][0]["delta"].get("content")
        for chunk in chunks
        if chunk["choices"][0]["delta"].get("content") is not None
    ]
    progress = [
        chunk["choices"][0]["delta"].get("reasoning_content")
        for chunk in chunks
        if chunk["choices"][0]["delta"].get("reasoning_content") is not None
    ]
    assert progress[0] == "正在解析对话与图片输入。\n"
    assert any("文生图模式" in item for item in progress)
    assert any("提示词改写完成：画一只猫" in item for item in progress)
    assert any(isinstance(content, list) for content in contents)
    assert text.rstrip().endswith("data: [DONE]")


def test_openai_stream_without_thinking_uses_content_for_progress() -> None:
    with TestClient(app).stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "画一只猫"}],
            "stream": True,
            "thinking": False,
            "dry_run": True,
        },
    ) as response:
        response.read()
        chunks = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: {")
        ]
    deltas = [chunk["choices"][0]["delta"] for chunk in chunks]
    assert not any("reasoning_content" in delta for delta in deltas)
    assert any(delta.get("content") == "正在解析对话与图片输入。\n" for delta in deltas)
    assert any(isinstance(delta.get("content"), list) for delta in deltas)


def test_model_probe_does_not_generate() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )
    assert response.status_code == 200
    assert isinstance(response.json()["choices"][0]["message"]["content"], str)
