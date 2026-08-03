from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src.agents.comfyui_image_to_video import MODEL_ID
from src.agents.comfyui_image_to_video.inputs import parse_input
from src.agents.comfyui_image_to_video.openai_compatible_api import create_app
from src.agents.comfyui_image_to_video.rewriter import (
    GPUStackPromptRewriter,
    PromptRewriteError,
)
from src.agents.comfyui_image_to_video.schemas import (
    ImageToVideoOptions,
    ParsedImageToVideoRequest,
)
from src.agents.comfyui_image_to_video.settings import ImageToVideoSettings
from src.agents.comfyui_image_to_video.workflow import ImageToVideoWorkflowRenderer
from src.agents.comfyui_video_generation.client import ComfyUIClient, JobInspection
from src.agents.openai_compatible import OpenAIChatMessage

PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def settings(**updates: Any) -> ImageToVideoSettings:
    values: dict[str, Any] = {
        "comfyui_i2v_base_url": "http://comfy.test:8188",
        "comfyui_i2v_public_base_url": "http://comfy.public:8188",
        "comfyui_i2v_poll_interval_seconds": 0.01,
        "comfyui_i2v_max_wait_seconds": 2,
    }
    values.update(updates)
    return ImageToVideoSettings(**values)


def messages(prompt: str = "让猫咪转头看向镜头，5秒，25fps") -> list[OpenAIChatMessage]:
    return [
        OpenAIChatMessage(
            role="user",
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": PNG_DATA_URL}},
            ],
        )
    ]


def test_natural_language_parameters_and_explicit_options() -> None:
    parsed = parse_input(
        messages("生成竖屏1080p视频，12秒，30fps，seed=7"),
        ImageToVideoOptions(seconds=6, seed=42),
        settings(),
    )

    assert parsed.size == "1080x1920"
    assert parsed.seconds == 6
    assert parsed.fps == 30
    assert parsed.seed == 42


def test_rejects_duration_over_hard_limit_and_unknown_size() -> None:
    with pytest.raises(ValueError, match="不能超过 15 秒"):
        parse_input(messages("让猫咪走动，16秒"), ImageToVideoOptions(), settings())
    with pytest.raises(ValueError, match="不支持的视频尺寸"):
        parse_input(
            messages("让猫咪走动，1000x700"),
            ImageToVideoOptions(),
            settings(),
        )


def test_requires_input_image() -> None:
    with pytest.raises(ValueError, match="上传一张输入图片"):
        parse_input(
            [OpenAIChatMessage(role="user", content="让猫咪走动")],
            ImageToVideoOptions(),
            settings(),
        )


def test_workflow_renderer_changes_allowlisted_i2v_inputs() -> None:
    renderer = ImageToVideoWorkflowRenderer(settings().comfyui_i2v_workflow_path)
    original = json.dumps(renderer.template, sort_keys=True)
    request = ParsedImageToVideoRequest(
        prompt="cat moves",
        rewritten_prompt="The cat turns naturally toward the camera.",
        negative_prompt="distortion",
        size="1280x720",
        seconds=5,
        fps=25,
        seed=42,
        second_seed=43,
    )

    rendered = renderer.render(
        request,
        uploaded_image="video_i2v_test.png",
        video_id="video_i2v_test",
    )

    assert rendered["269"]["inputs"]["image"] == "video_i2v_test.png"
    assert rendered["320:312"]["inputs"]["value"] == 1280
    assert rendered["320:299"]["inputs"]["value"] == 720
    assert rendered["320:301"]["inputs"]["value"] == 5
    assert rendered["320:300"]["inputs"]["value"] == 25
    assert rendered["320:276"]["inputs"]["noise_seed"] == 42
    assert rendered["320:277"]["inputs"]["noise_seed"] == 43
    assert rendered["320:319"]["inputs"]["value"].startswith("The cat")
    assert rendered["320:313"]["inputs"]["text"] == "distortion"
    assert rendered["320:328"]["inputs"]["value"] is False
    assert rendered["75"]["inputs"]["filename_prefix"].endswith("video_i2v_test")
    assert json.dumps(renderer.template, sort_keys=True) == original


@pytest.mark.asyncio
async def test_visual_llm_rewriter_receives_image_and_cannot_return_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GPU_STACK_BASE_URL", "http://gpu.test/v1")
    monkeypatch.setenv("GPU_STACK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3.6-35b-a3b"
        content = payload["messages"][1]["content"]
        assert content[1]["image_url"]["url"] == PNG_DATA_URL
        assert "15秒" in content[0]["text"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"rewritten_prompt": "The cat walks forward."}
                            )
                        }
                    }
                ]
            },
        )

    rewriter = GPUStackPromptRewriter(
        settings(),
        transport=httpx.MockTransport(handler),
    )
    rewritten = await rewriter.rewrite(
        instruction="让猫向前走",
        history="",
        image_data_url=PNG_DATA_URL,
        size="1280x720",
        seconds=15,
        fps=25,
    )
    assert rewritten == "The cat walks forward."


@pytest.mark.asyncio
async def test_visual_llm_rewriter_normalizes_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GPU_STACK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.agents.comfyui_image_to_video.rewriter.gpu_stack_connection",
        lambda: (_ for _ in ()).throw(RuntimeError("missing GPU_STACK_API_KEY")),
    )

    with pytest.raises(PromptRewriteError, match="API Key未配置"):
        await GPUStackPromptRewriter(settings()).rewrite(
            instruction="move forward",
            history="",
            image_data_url=PNG_DATA_URL,
            size="1280x720",
            seconds=5,
            fps=25,
        )


@pytest.mark.asyncio
async def test_shared_client_uploads_image_to_comfyui() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/upload/image"
        assert b'filename="video_i2v_test.png"' in request.content
        return httpx.Response(
            200,
            json={"name": "video_i2v_test.png", "subfolder": "agent", "type": "input"},
        )

    client = ComfyUIClient(
        base_url="http://comfy.test:8188",
        public_base_url="http://comfy.public:8188",
        transport=httpx.MockTransport(handler),
    )
    try:
        uploaded = await client.upload_image(
            b"\x89PNG\r\n\x1a\ncontent",
            filename="video_i2v_test.png",
            content_type="image/png",
        )
    finally:
        await client.close()
    assert uploaded == "agent/video_i2v_test.png"


class FakeRewriter:
    def __init__(self) -> None:
        self.calls = 0

    async def rewrite(self, **kwargs: Any) -> str:
        self.calls += 1
        assert kwargs["image_data_url"].startswith("data:image/png;base64,")
        return "The cat turns toward the camera while the camera slowly pushes in."


class FakeComfyUIClient:
    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.upload_count = 0
        self.submit_count = 0

    async def health(self) -> bool:
        return self.healthy

    async def close(self) -> None:
        return None

    async def upload_image(self, data: bytes, **kwargs: Any) -> str:
        self.upload_count += 1
        assert data.startswith(b"\x89PNG")
        return "agent/input.png"

    async def submit(self, workflow: dict[str, Any]) -> str:
        self.submit_count += 1
        assert workflow["269"]["inputs"]["image"] == "agent/input.png"
        return "prompt-i2v"

    async def inspect(self, prompt_id: str) -> JobInspection:
        return JobInspection(
            status="completed",
            progress=100,
            output_url="http://comfy.public:8188/view?filename=result.mp4&type=output",
        )


def request_body(**updates: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": MODEL_ID,
        "messages": [message.model_dump() for message in messages()],
        "video": {"size": "1280x720", "seconds": 5, "fps": 25, "seed": 42},
    }
    body.update(updates)
    return body


def test_openai_completion_rewrites_uploads_and_submits() -> None:
    fake_client = FakeComfyUIClient()
    fake_rewriter = FakeRewriter()
    with TestClient(
        create_app(settings(), client=fake_client, rewriter=fake_rewriter)
    ) as client:
        response = client.post("/v1/chat/completions", json=request_body())

    assert response.status_code == 200
    message = response.json()["choices"][0]["message"]
    assert "图生视频已生成完成" in message["content"]
    assert "comfy.public" not in message["content"]
    assert message["video"]["status"] == "completed"
    assert message["video"]["source_url"].startswith("http://comfy.public")
    assert message["video"]["seconds"] == 5
    assert fake_rewriter.calls == 1
    assert fake_client.upload_count == 1
    assert fake_client.submit_count == 1


def test_dry_run_does_not_download_rewrite_upload_or_submit() -> None:
    fake_client = FakeComfyUIClient()
    fake_rewriter = FakeRewriter()
    with TestClient(
        create_app(settings(), client=fake_client, rewriter=fake_rewriter)
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            json=request_body(
                dry_run=True,
                input_image="http://unreachable.invalid/input.png",
                messages=[{"role": "user", "content": "让图片自然动起来，5秒"}],
            ),
        )

    assert response.status_code == 200
    assert "未下载图片" in response.json()["choices"][0]["message"]["content"]
    assert fake_rewriter.calls == 0
    assert fake_client.upload_count == 0
    assert fake_client.submit_count == 0


def test_openai_stream_emits_rewrite_progress_video_and_done() -> None:
    fake_client = FakeComfyUIClient()
    fake_rewriter = FakeRewriter()
    with TestClient(
        create_app(settings(), client=fake_client, rewriter=fake_rewriter)
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            json=request_body(stream=True, thinking=True),
        )

    assert response.status_code == 200
    assert "reasoning_content" in response.text
    assert "视觉LLM改写" in response.text
    assert '"source_url": "http://comfy.public' in response.text
    assert "data: [DONE]" in response.text


def test_readiness_and_unknown_model_contract() -> None:
    fake_client = FakeComfyUIClient()
    with TestClient(
        create_app(settings(), client=fake_client, rewriter=FakeRewriter())
    ) as client:
        readiness = client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hello"}]},
        )
        empty_readiness = client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": []},
        )
        unknown = client.post(
            "/v1/chat/completions",
            json=request_body(model="unknown-model"),
        )

    assert readiness.status_code == 200
    assert "上传一张图片" in readiness.json()["choices"][0]["message"]["content"]
    assert empty_readiness.status_code == 200
    assert "上传一张图片" in empty_readiness.json()["choices"][0]["message"]["content"]
    assert unknown.status_code == 404
