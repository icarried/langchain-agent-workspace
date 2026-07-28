from __future__ import annotations

import json

import httpx
import pytest

from scripts.test_ai_app_video_agent import (
    ModelTestError,
    chat_completions_url,
    extract_download_url,
    iter_sse_data,
    stream_model_chat,
)


def test_chat_completions_url_accepts_gateway_base_variants() -> None:
    assert chat_completions_url("http://gateway:8008") == (
        "http://gateway:8008/v1/chat/completions"
    )
    assert chat_completions_url("http://gateway:8008/v1") == (
        "http://gateway:8008/v1/chat/completions"
    )


def test_iter_sse_data_parses_openai_blocks() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"完成"}}]}',
        "",
        "data: [DONE]",
        "",
    ]
    assert list(iter_sse_data(lines)) == [
        '{"choices":[{"delta":{"content":"完成"}}]}',
        "[DONE]",
    ]


def test_stream_model_chat_sends_ai_platform_upstream_payload_without_auth() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        stream = (
            'data: {"choices":[{"delta":{"reasoning_content":"已解析"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"[下载视频](http://comfy/view?a=1)",'
            '"video":{"content_url":"http://comfy/view?a=1"}}}]}\n\n'
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            text=stream,
            headers={"content-type": "text/event-stream"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = stream_model_chat(
            client,
            base_url="http://gateway.test:8008/v1",
            model="comfyui-video-generation-agent",
            prompt="生成一个猫咪视频",
            max_wait_seconds=600,
        )

    assert captured["url"] == "http://gateway.test:8008/v1/chat/completions"
    assert captured["authorization"] is None
    assert captured["payload"] == {
        "model": "comfyui-video-generation-agent",
        "messages": [{"role": "user", "content": "生成一个猫咪视频"}],
        "stream": True,
        "thinking": True,
        "wait_for_completion": True,
        "max_wait_seconds": 600,
    }
    assert result.reasoning == "已解析"
    assert extract_download_url(result.content, result.video) == (
        "http://comfy/view?a=1"
    )
    assert result.completed is True


def test_stream_model_chat_adds_optional_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        stream_model_chat(
            client,
            base_url="http://gateway.test:8008/v1",
            model="comfyui-video-generation-agent",
            prompt="生成一个猫咪视频",
            api_key="secret",
        )


def test_stream_model_chat_rejects_agent_error_rendered_as_content() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"ComfyUI拒绝了工作流"}}]}\n\n'
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ModelTestError, match="ComfyUI拒绝了工作流"):
            stream_model_chat(
                client,
                base_url="http://gateway.test:8008/v1",
                model="comfyui-video-generation-agent",
                prompt="生成一个猫咪视频",
            )
