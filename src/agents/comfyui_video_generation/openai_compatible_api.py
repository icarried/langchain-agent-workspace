from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field

from src.agents.openai_compatible import OpenAIChatCompletionRequest, model_list

from .client import ComfyUIClient, ComfyUIRequestError
from .inputs import is_readiness_probe
from .schemas import VideoGenerationResult, VideoOptions
from .service import VideoGenerationProgress, VideoGenerationService
from .settings import VideoGenerationSettings

MODEL_ID = "comfyui-video-generation-agent"


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID
    video: VideoOptions = Field(default_factory=VideoOptions)
    wait_for_completion: bool = True
    max_wait_seconds: float | None = Field(default=None, gt=0)


def create_app(
    settings: VideoGenerationSettings | None = None,
    *,
    client: ComfyUIClient | Any | None = None,
) -> FastAPI:
    selected = settings or VideoGenerationSettings()
    owns_client = client is None
    selected_client = client or ComfyUIClient(selected)
    service = VideoGenerationService(selected, selected_client)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_client:
                await selected_client.close()

    application = FastAPI(
        title="Direct ComfyUI Video Generation Agent",
        version="0.1.0",
        description="LangGraph LTX 2.3 video generation worker that calls ComfyUI directly.",
        lifespan=lifespan,
    )

    @application.get("/health")
    async def health() -> JSONResponse:
        ready = await selected_client.health()
        return JSONResponse(
            {
                "status": "ok" if ready else "degraded",
                "agent": "comfyui-video-generation",
                "model": MODEL_ID,
                "comfyui": "ready" if ready else "unavailable",
            },
            status_code=200 if ready else 503,
        )

    @application.get("/v1/models")
    async def list_models() -> dict[str, Any]:
        return model_list(MODEL_ID)

    @application.post("/v1/chat/completions")
    async def create_chat_completion(request: ChatCompletionRequest) -> Any:
        if request.model != MODEL_ID:
            raise HTTPException(
                status_code=404, detail=f"model not found: {request.model}"
            )
        if is_readiness_probe(request.messages):
            content = (
                "comfyui-video-generation-agent 已就绪。"
                "请描述要生成的视频，可指定尺寸、时长、FPS和随机种子。"
            )
            if request.stream:
                return _streaming_response(
                    _stream_text(content, request.model, thinking=request.thinking)
                )
            return _completion_response(request.model, content)
        if request.stream:
            return _streaming_response(_stream_generation(service, request))
        try:
            result = await service.run(
                request.messages,
                request.video,
                dry_run=request.dry_run,
                wait_for_completion=request.wait_for_completion,
                max_wait_seconds=request.max_wait_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ComfyUIRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail="视频生成服务暂时不可用"
            ) from exc
        return _completion_response(
            request.model, result.text, video=_video_metadata(result)
        )

    return application


async def _stream_generation(
    service: VideoGenerationService, request: ChatCompletionRequest
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    yield _sse_delta(completion_id, created, request.model, role="assistant")
    try:
        async for event in service.stream(
            request.messages,
            request.video,
            dry_run=request.dry_run,
            wait_for_completion=request.wait_for_completion,
            max_wait_seconds=request.max_wait_seconds,
        ):
            if isinstance(event, VideoGenerationProgress):
                yield _sse_delta(
                    completion_id,
                    created,
                    request.model,
                    content=event.message,
                    channel="reasoning_content" if request.thinking else "content",
                )
            else:
                yield _sse_delta(
                    completion_id,
                    created,
                    request.model,
                    content=event.text,
                    video=_video_metadata(event),
                )
    except ValueError as exc:
        yield _sse_delta(completion_id, created, request.model, content=str(exc))
    except ComfyUIRequestError as exc:
        yield _sse_delta(completion_id, created, request.model, content=str(exc))
    except Exception:
        yield _sse_delta(
            completion_id, created, request.model, content="视频生成服务暂时不可用"
        )
    yield _sse_done(completion_id, created, request.model)
    yield "data: [DONE]\n\n"


async def _stream_text(
    content: str, model: str, *, thinking: bool
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    yield _sse_delta(completion_id, created, model, role="assistant")
    yield _sse_delta(
        completion_id,
        created,
        model,
        content=content,
        channel="reasoning_content" if thinking else "content",
    )
    yield _sse_done(completion_id, created, model)
    yield "data: [DONE]\n\n"


def _streaming_response(generator: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _completion_response(
    model: str,
    content: str,
    *,
    video: dict[str, Any] | None = None,
) -> JSONResponse:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if video is not None:
        message["video"] = video
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


def _video_metadata(result: VideoGenerationResult) -> dict[str, Any]:
    return {
        "id": result.video_id,
        "status": result.status,
        "progress": result.progress,
        "prompt_id": result.prompt_id,
        "content_url": result.content_url,
    }


def _sse_delta(
    completion_id: str,
    created: int,
    model: str,
    *,
    role: Literal["assistant"] | None = None,
    content: Any = None,
    channel: Literal["content", "reasoning_content"] = "content",
    video: dict[str, Any] | None = None,
) -> str:
    delta: dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content is not None:
        delta[channel] = content
    if video is not None:
        delta["video"] = video
    return (
        "data: "
        + json.dumps(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            ensure_ascii=False,
        )
        + "\n\n"
    )


def _sse_done(completion_id: str, created: int, model: str) -> str:
    return (
        "data: "
        + json.dumps(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
        )
        + "\n\n"
    )


app = create_app()
