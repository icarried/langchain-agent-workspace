from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
import queue
import re
import threading
import time
import traceback
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field

from src.agents.openai_compatible import (
    OpenAIChatCompletionRequest,
    OpenAIChatMessage,
    model_list,
)
from src.agents.openai_compatible_inputs import (
    AttachmentReference,
    attachment_reference_from_value,
    dedupe_attachment_references,
    message_content_to_text_and_attachments,
)
from src.document_ocr.gpu_stack import OCRRequestError
from src.knowledge_base.manager import RebuildRequiredError

from .constants import MODEL_ID
from .departments import DEPARTMENTS
from .intent import IntentRecognitionError
from .schemas import AgentResult, ProgressEvent
from .service import DepartmentKnowledgeBaseAgent


READINESS_TEXT = (
    "department-knowledge-base-agent 已就绪。业务请求必须由平台传入固定 "
    "knowledge_id；可直接提问，或上传附件并明确说明“保存到知识库”。"
)
LOGGER = logging.getLogger(__name__)


class ChatMessage(OpenAIChatMessage):
    pass


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID
    messages: list[ChatMessage] = Field(default_factory=list)
    knowledge_id: str | None = None
    files: list[str | dict[str, Any]] = Field(default_factory=list)
    top_k: int | None = Field(default=None, ge=1, le=20)


agent = DepartmentKnowledgeBaseAgent()
app = FastAPI(
    title="Department Knowledge Base OpenAI-compatible API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, Any]:
    settings = agent.runtime.settings
    task_stats = agent.runtime.import_tasks.stats()
    return {
        "status": "ok",
        "agent": "department-knowledge-base",
        "model": MODEL_ID,
        "knowledge_spaces": len(DEPARTMENTS),
        "gpu_stack_configured": bool(os.getenv("GPU_STACK_API_KEY", "").strip()),
        "object_store_enabled": settings.object_store_enabled,
        "object_store_configured": bool(
            settings.minio_access_key and settings.minio_secret_key
        ),
        "query_rewrite_enabled": settings.query_rewrite_enabled,
        **task_stats,
    }


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return model_list(MODEL_ID)


@app.get("/v1/knowledge-spaces")
def list_knowledge_spaces() -> dict[str, Any]:
    return {
        "data": [
            {
                "knowledge_id": item.knowledge_id,
                "display_name": item.display_name,
            }
            for item in DEPARTMENTS.values()
        ]
    }


@app.post("/v1/chat/completions")
def create_chat_completion(request: ChatCompletionRequest) -> Any:
    if request.model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"model not found: {request.model}")
    text, sources = _last_user_input(request)
    if _is_readiness_probe(text, sources):
        if request.stream:
            return _streaming_response(
                _stream_text(READINESS_TEXT, request.model, thinking=request.thinking)
            )
        return _completion(request.model, READINESS_TEXT)
    if not request.knowledge_id:
        raise HTTPException(
            status_code=400,
            detail="knowledge_id is required for department knowledge-base requests",
        )
    if len(sources) > agent.runtime.settings.max_files_per_request:
        raise HTTPException(
            status_code=400,
            detail=(
                "too many files; maximum is "
                f"{agent.runtime.settings.max_files_per_request}"
            ),
        )

    if request.stream:
        return _streaming_response(_stream_request(request, text, sources))
    try:
        result = agent.invoke(
            knowledge_id=request.knowledge_id,
            text=text,
            sources=sources,
            top_k=request.top_k,
            dry_run=request.dry_run,
        )
    except ValueError as exc:
        _log_request_failure(request.knowledge_id, "invoke", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RebuildRequiredError as exc:
        _log_request_failure(request.knowledge_id, "invoke", exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (IntentRecognitionError, OCRRequestError) as exc:
        _log_request_failure(request.knowledge_id, "invoke", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _log_request_failure(request.knowledge_id, "invoke", exc)
        raise HTTPException(
            status_code=503,
            detail="department knowledge-base service is temporarily unavailable",
        ) from exc
    return _completion(request.model, result.content, result=result)


def _last_user_input(
    request: ChatCompletionRequest,
) -> tuple[str, list[AttachmentReference]]:
    text = ""
    attachments: list[AttachmentReference] = []
    for message in reversed(request.messages):
        if message.role != "user":
            continue
        text, content_attachments = message_content_to_text_and_attachments(
            message.content
        )
        attachments.extend(content_attachments)
        break
    attachments.extend(
        AttachmentReference(url=url, source_kind="message_text")
        for url in _http_urls(text)
    )
    attachments.extend(
        reference
        for item in request.files
        if (
            reference := attachment_reference_from_value(
                item,
                source_kind="top_level_files",
            )
        )
        is not None
    )
    return _redact_http_urls(text).strip(), dedupe_attachment_references(attachments)


def _http_urls(text: str) -> list[str]:
    return [
        match.rstrip("，,。；;）)]}")
        for match in re.findall(r"https?://[^\s\"'<>，]+", text)
    ]


def _redact_http_urls(text: str) -> str:
    return re.sub(r"https?://[^\s\"'<>，]+", "[附件URL]", text)


def _is_readiness_probe(text: str, sources: list[AttachmentReference]) -> bool:
    return not sources and text.strip().lower() in {
        "",
        "hello",
        "hi",
        "test",
        "你好",
        "测试",
    }


def _stream_request(
    request: ChatCompletionRequest,
    text: str,
    sources: list[AttachmentReference],
) -> Generator[str, None, None]:
    completion_id, created = _stream_identity()
    request_id = uuid.uuid4().hex
    yield _sse_delta(completion_id, created, request.model, role="assistant")
    channel: Literal["content", "reasoning_content"] = (
        "reasoning_content" if request.thinking else "content"
    )
    yield _sse_delta(
        completion_id,
        created,
        request.model,
        content=(
            f"已接收请求，知识空间为 {request.knowledge_id}，"
            f"附件数量为 {len(sources)}。\n"
        ),
        channel=channel,
    )
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    state = {"stage": "accepted"}

    def report(event: ProgressEvent) -> None:
        state["stage"] = event.stage
        events.put(("progress", event))

    def run() -> None:
        try:
            result = agent.invoke(
                knowledge_id=request.knowledge_id or "",
                text=text,
                sources=sources,
                top_k=request.top_k,
                dry_run=request.dry_run,
                progress=report,
            )
        except Exception as exc:
            LOGGER.error(
                "department knowledge-base request failed request_id=%s "
                "knowledge_id=%s stage=%s exception_type=%s\n%s",
                request_id,
                request.knowledge_id,
                state["stage"],
                type(exc).__name__,
                _redact_traceback(traceback.format_exc()),
            )
            events.put(("error", exc))
        else:
            events.put(("result", result))

    threading.Thread(
        target=run,
        name=f"department-kb-{request_id[:8]}",
        daemon=True,
    ).start()

    while True:
        try:
            kind, payload = events.get(
                timeout=agent.runtime.settings.stream_heartbeat_seconds
            )
        except queue.Empty:
            yield _sse_delta(
                completion_id,
                created,
                request.model,
                content=f"仍在处理，当前阶段：{state['stage']}。\n",
                channel=channel,
            )
            continue
        if kind == "progress":
            yield _sse_delta(
                completion_id,
                created,
                request.model,
                content=f"{payload.message}\n",
                channel=channel,
            )
            continue
        if kind == "result":
            result = payload
            content = result.content
            break
        exc = payload
        if isinstance(
            exc,
            (
                ValueError,
                IntentRecognitionError,
                OCRRequestError,
                RebuildRequiredError,
            ),
        ):
            content = str(exc)
        else:
            content = (
                "部门知识库服务暂时不可用；本次索引未提交，"
                "此前已发布的知识库快照保持不变。"
            )
        yield _sse_delta(
            completion_id,
            created,
            request.model,
            content="本次处理失败，索引未提交。\n",
            channel=channel,
        )
        break
    file_payloads, download_notice = (
        _source_file_payloads(result) if kind == "result" else ([], None)
    )
    if download_notice:
        content += f"\n\n{download_notice}"
    yield _sse_delta(
        completion_id,
        created,
        request.model,
        content=content,
    )
    for file_payload in file_payloads:
        yield _sse_delta(
            completion_id,
            created,
            request.model,
            file_payload=file_payload,
        )
    yield _sse_done(completion_id, created, request.model)
    yield "data: [DONE]\n\n"


def _redact_traceback(value: str) -> str:
    return re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[REDACTED]", value)


def _log_request_failure(
    knowledge_id: str | None,
    stage: str,
    exc: Exception,
) -> None:
    LOGGER.error(
        "department knowledge-base request failed request_id=%s "
        "knowledge_id=%s stage=%s exception_type=%s\n%s",
        uuid.uuid4().hex,
        knowledge_id,
        stage,
        type(exc).__name__,
        _redact_traceback(traceback.format_exc()),
    )


def _stream_text(
    content: str,
    model: str,
    *,
    thinking: bool,
) -> Generator[str, None, None]:
    completion_id, created = _stream_identity()
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


def _completion(
    model: str,
    content: str,
    *,
    result: AgentResult | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
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
    if result is not None:
        files, download_notice = _source_file_payloads(result)
        if download_notice:
            payload["choices"][0]["message"]["content"] += f"\n\n{download_notice}"
        payload["knowledge_id"] = result.knowledge_id
        payload["department"] = result.department
        payload["intent"] = result.intent.value
        payload["choices"][0]["message"]["files"] = files
    return JSONResponse(payload)


def _stream_identity() -> tuple[str, int]:
    return f"chatcmpl-{uuid.uuid4().hex}", int(time.time())


def _sse_delta(
    completion_id: str,
    created: int,
    model: str,
    *,
    role: Literal["assistant"] | None = None,
    content: Any = None,
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


def _source_file_payloads(
    result: AgentResult,
) -> tuple[list[dict[str, Any]], str | None]:
    """Encode current source originals using the platform's existing file contract."""

    if result.intent.value != "query" or not result.source_documents:
        return [], None
    settings = agent.runtime.settings
    directory = agent.runtime.manager.active_documents_dir(result.knowledge_id)
    payloads: list[dict[str, Any]] = []
    total_bytes = 0
    omitted = 0
    for source in result.source_documents[: settings.max_download_files]:
        filename = Path(source.filename.replace("\\", "/")).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {
            ".bmp",
            ".doc",
            ".docx",
            ".jpeg",
            ".jpg",
            ".markdown",
            ".md",
            ".pdf",
            ".png",
            ".tif",
            ".tiff",
            ".txt",
            ".webp",
        }:
            continue
        path = (directory / filename).resolve()
        if directory.resolve() not in path.parents or not path.is_file():
            omitted += 1
            LOGGER.warning(
                "source download skipped knowledge_id=%s filename=%s reason=missing",
                result.knowledge_id,
                filename,
            )
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if source.sha256 and digest != source.sha256:
            omitted += 1
            LOGGER.warning(
                "source download skipped knowledge_id=%s filename=%s reason=sha_mismatch",
                result.knowledge_id,
                filename,
            )
            continue
        if (
            suffix
            in {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
            and len(data) > settings.max_download_image_bytes
        ):
            omitted += 1
            continue
        if total_bytes + len(data) > settings.max_download_bytes:
            omitted += 1
            break
        total_bytes += len(data)
        payloads.append(
            {
                "status": "completed",
                "filename": filename,
                "file_type": suffix.removeprefix("."),
                "mime_type": (
                    mimetypes.guess_type(filename)[0]
                    or "application/octet-stream"
                ),
                "encoding": "base64",
                "content_base64": base64.b64encode(data).decode("ascii"),
                "sha256": digest,
                "size": len(data),
            }
        )
    notice = (
        f"有 {omitted} 份来源原件因大小或校验限制未附加下载，请缩小检索范围或联系管理员。"
        if omitted
        else None
    )
    return payloads, notice


def _streaming_response(generator: Generator[str, None, None]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
