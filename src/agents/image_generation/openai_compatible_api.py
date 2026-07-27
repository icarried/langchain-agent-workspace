from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Generator
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from src.agents.openai_compatible import OpenAIChatCompletionRequest, OpenAIChatMessage, model_list

from .client import GPUStackRequestError
from .inputs import is_readiness_probe
from .service import (
    ImageGenerationProgress,
    ImageGenerationResult,
    generate_image,
    generate_image_with_progress,
)


MODEL_ID = "image-generation-agent"


class ChatMessage(OpenAIChatMessage):
    pass


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID


app = FastAPI(
    title="Conversational Image Generation OpenAI-compatible API",
    version="0.1.0",
    description="Qwen3.5 prompt rewriting with Qwen image generation and editing.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "image-generation", "model": MODEL_ID}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return model_list(MODEL_ID)


@app.post("/v1/chat/completions")
def create_chat_completion(request: ChatCompletionRequest) -> Any:
    if request.model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"model not found: {request.model}")
    if is_readiness_probe(request.messages):
        content = _readiness_message()
        if request.stream:
            return _streaming_response(
                stream_text_response(content, request.model, thinking=request.thinking)
            )
        return _chat_completion_response(request.model, content)

    if request.stream:
        return _streaming_response(
            stream_image_generation(
                request.messages,
                request.model,
                dry_run=request.dry_run,
                thinking=request.thinking,
            )
        )
    try:
        result = generate_image(request.messages, dry_run=request.dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GPUStackRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="图片生成服务暂时不可用") from exc
    return _chat_completion_response(request.model, result.content_parts())


def stream_image_generation(
    messages: list[ChatMessage],
    model: str,
    *,
    dry_run: bool,
    thinking: bool,
) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(
        target=_run_generation,
        args=(messages, dry_run, events),
        daemon=True,
    )
    worker.start()

    yield _sse_delta(completion_id, created, model, role="assistant")
    active_stage = "启动图片任务"
    while True:
        try:
            kind, payload = events.get(timeout=5)
        except queue.Empty:
            yield _sse_delta(
                completion_id,
                created,
                model,
                content=f"正在{active_stage}，请稍候。\n",
                channel="reasoning_content" if thinking else "content",
            )
            continue
        if kind == "progress":
            progress: ImageGenerationProgress = payload
            active_stage = progress.heartbeat
            yield _sse_delta(
                completion_id,
                created,
                model,
                content=progress.message,
                channel="reasoning_content" if thinking else "content",
            )
            continue
        if kind == "result":
            result: ImageGenerationResult = payload
            yield _sse_delta(
                completion_id,
                created,
                model,
                content=result.content_parts(),
            )
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return
        message = str(payload) if kind == "input_error" else "图片生成服务暂时不可用"
        yield _sse_delta(completion_id, created, model, content=message)
        yield _sse_done(completion_id, created, model)
        yield "data: [DONE]\n\n"
        return


def stream_text_response(
    content: str,
    model: str,
    *,
    thinking: bool,
) -> Generator[str, None, None]:
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


def _run_generation(
    messages: list[ChatMessage],
    dry_run: bool,
    events: queue.Queue[tuple[str, Any]],
) -> None:
    def report(progress: ImageGenerationProgress) -> None:
        events.put(("progress", progress))

    try:
        events.put(
            (
                "result",
                generate_image_with_progress(
                    messages,
                    dry_run=dry_run,
                    progress=report,
                ),
            )
        )
    except ValueError as exc:
        events.put(("input_error", str(exc)))
    except Exception:
        events.put(("service_error", "图片生成服务暂时不可用"))


def _streaming_response(generator: Generator[str, None, None]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _chat_completion_response(model: str, content: Any) -> JSONResponse:
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


def _sse_delta(
    completion_id: str,
    created: int,
    model: str,
    *,
    role: Literal["assistant"] | None = None,
    content: Any = None,
    channel: Literal["content", "reasoning_content"] = "content",
) -> str:
    delta: dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content is not None:
        delta[channel] = content
    return "data: " + json.dumps(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        },
        ensure_ascii=False,
    ) + "\n\n"


def _sse_done(completion_id: str, created: int, model: str) -> str:
    return "data: " + json.dumps(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
        ensure_ascii=False,
    ) + "\n\n"


def _readiness_message() -> str:
    return (
        "image-generation-agent 已就绪。请描述要生成的画面；"
        "上传一张图片时会进行编辑，后续对话可继续修改上一张生成图。"
    )
