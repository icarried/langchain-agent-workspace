from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src.agents.comfyui_video_generation.client import (
    ComfyUIClient,
    ComfyUIRequestError,
    JobInspection,
)
from src.agents.comfyui_video_generation.inputs import parse_video_request
from src.agents.comfyui_video_generation.openai_compatible_api import (
    MODEL_ID,
    create_app,
)
from src.agents.comfyui_video_generation.schemas import VideoOptions
from src.agents.comfyui_video_generation.settings import VideoGenerationSettings
from src.agents.comfyui_video_generation.workflow import WorkflowRenderer
from src.agents.openai_compatible import OpenAIChatMessage


def settings(**updates: Any) -> VideoGenerationSettings:
    values: dict[str, Any] = {
        "comfyui_video_base_url": "http://comfy.test:8188",
        "comfyui_video_public_base_url": "http://comfy.public:8188",
        "comfyui_video_poll_interval_seconds": 0.01,
        "comfyui_video_max_wait_seconds": 2,
    }
    values.update(updates)
    return VideoGenerationSettings(**values)


def test_parses_natural_language_and_explicit_options_win() -> None:
    messages = [
        OpenAIChatMessage(
            role="user",
            content="生成8秒、720x1280、30fps的海边骑行视频，随机种子7",
        )
    ]
    parsed = parse_video_request(
        messages,
        VideoOptions(seconds=5, seed=42, negative_prompt="blurry"),
        settings(),
    )

    assert parsed.prompt.startswith("生成8秒")
    assert parsed.size == "720x1280"
    assert parsed.seconds == 5
    assert parsed.fps == 30
    assert parsed.seed == 42
    assert parsed.negative_prompt == "blurry"


def test_workflow_renderer_changes_only_allowlisted_inputs() -> None:
    renderer = WorkflowRenderer(settings().comfyui_video_workflow_path)
    original = json.dumps(renderer.template, sort_keys=True)
    request = parse_video_request(
        [OpenAIChatMessage(role="user", content="cinematic cyclist")],
        VideoOptions(
            size="1280x720",
            seconds=5,
            fps=25,
            seed=42,
            second_seed=43,
            prompt_enhance=False,
        ),
        settings(),
    )

    rendered = renderer.render(request, "video_test")

    assert rendered["267:266"]["inputs"]["value"] == "cinematic cyclist"
    assert rendered["267:257"]["inputs"]["value"] == 1280
    assert rendered["267:258"]["inputs"]["value"] == 720
    assert rendered["267:225"]["inputs"]["value"] == 5
    assert rendered["267:260"]["inputs"]["value"] == 25
    assert rendered["267:237"]["inputs"]["noise_seed"] == 42
    assert rendered["267:216"]["inputs"]["noise_seed"] == 43
    assert rendered["267:330"]["inputs"]["value"] is False
    assert rendered["75"]["inputs"]["filename_prefix"] == "video/agent/video_test"
    assert json.dumps(renderer.template, sort_keys=True) == original


@pytest.mark.asyncio
async def test_client_preserves_bounded_comfyui_rejection_detail() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {"message": "Prompt outputs failed validation"},
                "node_errors": {"75": {"errors": [{"message": "bad output"}]}},
            },
        )

    client = ComfyUIClient(settings(), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ComfyUIRequestError) as raised:
            await client.submit({"75": {"class_type": "SaveVideo", "inputs": {}}})
        assert "Prompt outputs failed validation" in str(raised.value)
        assert "bad output" in str(raised.value)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_client_submits_and_extracts_completed_video_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"system": {"comfyui_version": "0.26.0"}})
        if request.url.path == "/prompt":
            body = json.loads(request.content)
            assert body["client_id"]
            assert "75" in body["prompt"]
            return httpx.Response(200, json={"prompt_id": "prompt-one"})
        if request.url.path == "/history/prompt-one":
            return httpx.Response(
                200,
                json={
                    "prompt-one": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "75": {
                                "videos": [
                                    {
                                        "filename": "video/agent/result.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        },
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = ComfyUIClient(settings(), transport=httpx.MockTransport(handler))
    try:
        assert await client.health() is True
        prompt_id = await client.submit(
            {"75": {"class_type": "SaveVideo", "inputs": {}}}
        )
        inspection = await client.inspect(prompt_id)
    finally:
        await client.close()

    assert inspection.status == "completed"
    assert inspection.progress == 100
    assert inspection.output_url is not None
    assert inspection.output_url.startswith("http://comfy.public:8188/view?")
    assert "result.mp4" in inspection.output_url


class FakeComfyUIClient:
    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.submit_count = 0
        self.inspect_count = 0

    async def health(self) -> bool:
        return self.healthy

    async def close(self) -> None:
        return None

    async def submit(self, workflow: dict[str, Any]) -> str:
        self.submit_count += 1
        self.workflow = workflow
        return "prompt-test"

    async def inspect(self, prompt_id: str) -> JobInspection:
        self.inspect_count += 1
        if self.inspect_count == 1:
            return JobInspection(status="in_progress", progress=10)
        return JobInspection(
            status="completed",
            progress=100,
            output_url="http://comfy.public:8188/view?filename=result.mp4&type=output",
        )


def request_body(**updates: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "生成5秒海边骑行视频"}],
        "video": {"size": "1280x720", "seconds": 5, "fps": 25, "seed": 42},
    }
    body.update(updates)
    return body


def test_openai_non_stream_completion_calls_comfyui_directly() -> None:
    fake = FakeComfyUIClient()
    with TestClient(create_app(settings(), client=fake)) as client:
        response = client.post("/v1/chat/completions", json=request_body())

    assert response.status_code == 200
    message = response.json()["choices"][0]["message"]
    assert "视频已生成完成" in message["content"]
    assert "comfy.public" not in message["content"]
    assert message["video"]["status"] == "completed"
    assert message["video"]["source_url"].startswith(
        "http://comfy.public:8188/view"
    )
    assert message["video"]["content_url"].startswith("http://comfy.public:8188/view")
    assert fake.submit_count == 1


def test_openai_stream_emits_progress_and_done() -> None:
    fake = FakeComfyUIClient()
    with TestClient(create_app(settings(), client=fake)) as client:
        response = client.post(
            "/v1/chat/completions",
            json=request_body(stream=True, thinking=True),
        )

    assert response.status_code == 200
    assert "reasoning_content" in response.text
    assert "视频已生成完成" in response.text
    assert '"source_url": "http://comfy.public:8188/view' in response.text
    assert "data: [DONE]" in response.text


def test_dry_run_does_not_call_comfyui() -> None:
    fake = FakeComfyUIClient()
    with TestClient(create_app(settings(), client=fake)) as client:
        response = client.post(
            "/v1/chat/completions",
            json=request_body(dry_run=True),
        )

    assert response.status_code == 200
    assert "dry-run" in response.json()["choices"][0]["message"]["content"]
    assert fake.submit_count == 0


def test_readiness_and_unhealthy_worker_contract() -> None:
    fake = FakeComfyUIClient(healthy=False)
    with TestClient(create_app(settings(), client=fake)) as client:
        health = client.get("/health")
        readiness = client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert health.status_code == 503
    assert readiness.status_code == 200
    assert "已就绪" in readiness.json()["choices"][0]["message"]["content"]


def test_unknown_model_returns_404() -> None:
    fake = FakeComfyUIClient()
    with TestClient(create_app(settings(), client=fake)) as client:
        response = client.post(
            "/v1/chat/completions",
            json=request_body(model="unknown-model"),
        )

    assert response.status_code == 404
