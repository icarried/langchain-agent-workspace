from __future__ import annotations

import base64
import json
import queue
import threading
import time
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.agents.openai_compatible import OpenAIChatCompletionRequest, OpenAIChatMessage
from src.agents.openai_compatible_inputs import (
    extract_labeled_paths,
    messages_to_text_and_urls,
)
from src.agents.remote_files import is_http_url, materialize_sources, remote_filename

from .fonts import inspect_required_fonts
from .service import format_official_document

MODEL_ID = "official-document-formatting-agent"


class ChatMessage(OpenAIChatMessage):
    pass


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID


class ParsedFormattingRequest(BaseModel):
    document_path: str
    dry_run: bool = False


app = FastAPI(
    title="Official Document Formatting OpenAI-compatible API",
    version="0.1.0",
    description="Deterministic company-approved DOCX formatting worker.",
)


@app.get("/health")
def health() -> dict[str, str]:
    inspection = inspect_required_fonts()
    return {
        "status": "ok",
        "agent": "official-document-formatting",
        "model": MODEL_ID,
        "fonts": "ready" if inspection.ready else "warning",
    }


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": 0,
                "owned_by": "local-agent-workspace",
            }
        ],
    }


@app.post("/v1/chat/completions")
def create_chat_completion(request: ChatCompletionRequest) -> Any:
    if request.model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"model not found: {request.model}")
    try:
        parsed = parse_document_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if parsed is None:
        content = _readiness_message()
        if request.stream:
            return _streaming_response(
                stream_text_response(content, request.model, thinking=request.thinking)
            )
        return _chat_completion_response(request.model, content)
    if request.stream:
        return _streaming_response(
            stream_chat_completion(parsed, request.model, thinking=request.thinking)
        )
    try:
        result = _run_format(parsed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="公文格式化服务暂时不可用") from exc
    file_payload = None if result["dry_run"] else _file_payload(result)
    return _chat_completion_response(
        request.model,
        result["report"],
        file_payload=file_payload,
    )


def parse_document_request(
    request: ChatCompletionRequest,
) -> ParsedFormattingRequest | None:
    text, content_part_urls = messages_to_text_and_urls(request.messages)
    document_paths = extract_labeled_paths(
        text,
        ["公文文件", "待格式化文件", "文件链接", "文件路径", "附件"],
        ["输出要求", "格式化要求"],
        extra_paths=content_part_urls,
    )
    if not document_paths:
        return None
    if len(document_paths) != 1:
        raise ValueError("公文格式化一次只能处理一份 DOCX 文件")
    return ParsedFormattingRequest(
        document_path=document_paths[0],
        dry_run=request.dry_run,
    )


def stream_text_response(
    content: str,
    model: str,
    *,
    thinking: bool = True,
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


def stream_chat_completion(
    formatting_request: ParsedFormattingRequest,
    model: str,
    *,
    thinking: bool = True,
) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(
        target=_run_format_worker,
        args=(formatting_request, events),
        daemon=True,
    )
    worker.start()

    progress_channel = "reasoning_content" if thinking else "content"
    yield _sse_delta(completion_id, created, model, role="assistant")
    yield _sse_delta(
        completion_id,
        created,
        model,
        content="已接收公文，开始执行公司标准格式化。\n",
        channel=progress_channel,
    )
    while True:
        try:
            kind, payload = events.get(timeout=10)
        except queue.Empty:
            yield _sse_delta(
                completion_id,
                created,
                model,
                content="公文格式化仍在进行，请稍候。\n",
                channel=progress_channel,
            )
            continue
        if kind == "result":
            result: dict[str, Any] = payload
            yield _sse_delta(
                completion_id,
                created,
                model,
                content=result["report"],
            )
            if not result["dry_run"]:
                yield _sse_delta(
                    completion_id,
                    created,
                    model,
                    file_payload=_file_payload(result),
                )
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return
        yield _sse_delta(
            completion_id,
            created,
            model,
            content=f"公文格式化失败：{payload}",
        )
        yield _sse_done(completion_id, created, model)
        yield "data: [DONE]\n\n"
        return


def _run_format_worker(
    formatting_request: ParsedFormattingRequest,
    events: queue.Queue[tuple[str, Any]],
) -> None:
    try:
        events.put(("result", _run_format(formatting_request)))
    except (FileNotFoundError, ValueError) as exc:
        events.put(("error", str(exc)))
    except Exception:  # noqa: BLE001 - worker boundary must return a sanitized error
        events.put(("error", "公文格式化服务暂时不可用"))


def _run_format(formatting_request: ParsedFormattingRequest) -> dict[str, Any]:
    source = formatting_request.document_path
    original_filename = (
        remote_filename(source) if is_http_url(source) else Path(source).name
    )
    with materialize_sources(
        [source],
        allowed_suffixes={".docx"},
        prefix="official-document-formatting-input-",
    ) as paths:
        return format_official_document(
            paths[0],
            original_filename=original_filename,
            dry_run=formatting_request.dry_run,
        )


def _file_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "filename": result["filename"],
        "file_type": "docx",
        "mime_type": result["mime_type"],
        "encoding": "base64",
        "content_base64": base64.b64encode(result["content"]).decode("ascii"),
        "sha256": result["sha256"],
        "size": result["size"],
    }


def _streaming_response(generator: Generator[str, None, None]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _chat_completion_response(
    model: str,
    content: str,
    *,
    file_payload: dict[str, Any] | None = None,
) -> JSONResponse:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if file_payload is not None:
        message["file"] = file_payload
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
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
    content: str | None = None,
    channel: Literal["content", "reasoning_content"] = "content",
    file_payload: dict[str, Any] | None = None,
) -> str:
    delta: dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content is not None:
        delta[channel] = content
    if file_payload is not None:
        delta["file"] = file_payload
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
        "official-document-formatting-agent 已就绪。\n\n"
        "请上传一份 DOCX，并使用以下格式：\n\n"
        "公文文件：\n<公文 DOCX 文件链接或服务端路径>\n\n"
        "该智能体只执行公司标准格式化，不润色或改写正文。"
    )
