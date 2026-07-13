from __future__ import annotations

import json
import queue
import re
import threading
import time
import uuid
from collections.abc import Generator
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.agents.openai_compatible_inputs import (
    dedupe,
    extract_json_array_paths,
    extract_labeled_paths,
    extract_paths_from_line,
    extract_section_block,
    messages_to_text_and_urls,
    message_content_to_text_and_urls,
    starts_section,
    strip_section_label,
)

from .service import review_official_document

MODEL_ID = "official-document-review-agent"


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = MODEL_ID
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    provider: str = "deepseek"
    review_model: str | None = None
    dry_run: bool = False
    thinking: bool = True


class ParsedDocumentRequest(BaseModel):
    document_path: str
    document_type: str = ""
    provider: str = "deepseek"
    review_model: str | None = None
    dry_run: bool = False


app = FastAPI(
    title="Official Document Review OpenAI-compatible API",
    version="0.1.0",
    description="OpenAI-compatible streaming adapter for FastGPT/Dify LLM nodes.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "official-document-review", "model": MODEL_ID}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "created": 0, "owned_by": "local-agent-workspace"}],
    }


@app.post("/v1/chat/completions")
def create_chat_completion(request: ChatCompletionRequest) -> Any:
    if request.model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"model not found: {request.model}")
    parsed = parse_document_request(request)
    if parsed is None:
        content = _readiness_message()
        if request.stream:
            return StreamingResponse(
                stream_text_response(content, request.model, thinking=request.thinking),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return _chat_completion_response(request.model, content)
    if request.stream:
        return StreamingResponse(
            stream_chat_completion(parsed, request.model, thinking=request.thinking),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    started = int(time.time())
    result = _run_review(parsed)
    return _chat_completion_response(request.model, result["report"], created=started)


def parse_document_request(request: ChatCompletionRequest) -> ParsedDocumentRequest | None:
    text, content_part_urls = messages_to_text_and_urls(request.messages)
    document_paths = _extract_paths_from_labeled_block(
        text,
        ["公文文件", "公文路径", "文件链接", "文件路径", "附件"],
        extra_paths=content_part_urls,
    )
    if not document_paths:
        return None
    return ParsedDocumentRequest(
        document_path=document_paths[0],
        document_type=_extract_scalar(text, ["公文类型", "文种"]) or "",
        provider=request.provider,
        review_model=request.review_model,
        dry_run=request.dry_run,
    )


def stream_text_response(content: str, model: str, *, thinking: bool = True) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    yield _sse_delta(completion_id, created, model, "assistant", "")
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        content,
        channel="reasoning_content" if thinking else "content",
    )
    yield _sse_done(completion_id, created, model)
    yield "data: [DONE]\n\n"


def stream_chat_completion(
    review_request: ParsedDocumentRequest,
    model: str,
    *,
    thinking: bool = True,
) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(target=_run_review_worker, args=(review_request, events), daemon=True)
    worker.start()

    yield _sse_delta(completion_id, created, model, "assistant", "")
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        "已接收 1 份公文，开始格式检查。\n\n",
        channel="reasoning_content" if thinking else "content",
    )
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        f"公文文件：{review_request.document_path}\n",
        channel="reasoning_content" if thinking else "content",
    )
    while True:
        try:
            kind, payload = events.get(timeout=15)
        except queue.Empty:
            yield _sse_delta(
                completion_id,
                created,
                model,
                None,
                "公文格式检查仍在进行...\n",
                channel="reasoning_content" if thinking else "content",
            )
            continue
        if kind == "result":
            yield _sse_delta(completion_id, created, model, None, payload["report"])
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return
        if kind == "error":
            yield _sse_delta(completion_id, created, model, None, f"公文格式检查失败：{payload}\n")
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return


def _run_review_worker(review_request: ParsedDocumentRequest, events: queue.Queue[tuple[str, Any]]) -> None:
    try:
        events.put(("result", _run_review(review_request)))
    except Exception as exc:
        events.put(("error", str(exc)))


def _run_review(review_request: ParsedDocumentRequest) -> dict[str, Any]:
    return review_official_document(
        review_request.document_path,
        document_type=review_request.document_type,
        provider=review_request.provider,
        model=review_request.review_model,
        dry_run=review_request.dry_run,
    )


def _chat_completion_response(model: str, content: str, *, created: int | None = None) -> JSONResponse:
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created or int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


def _readiness_message() -> str:
    return (
        "official-document-review-agent 已就绪。\n\n"
        "请在正式检查时提供以下格式：\n\n"
        "公文类型：通知\n\n"
        "公文文件：\n"
        "<公文文件链接或服务端路径>\n\n"
        "输出要求：请输出公文格式检查报告。"
    )


def _sse_delta(
    completion_id: str,
    created: int,
    model: str,
    role: Literal["assistant"] | None,
    content: str,
    *,
    channel: Literal["content", "reasoning_content"] = "content",
) -> str:
    delta: dict[str, str] = {}
    if role:
        delta["role"] = role
    if content:
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


def _sse_done(completion_id: str, created: int, model: str, *, finish_reason: str = "stop") -> str:
    return "data: " + json.dumps(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        },
        ensure_ascii=False,
    ) + "\n\n"


def _message_content_to_text(content: Any) -> str:
    return message_content_to_text_and_urls(content)[0]


def _extract_paths_from_labeled_block(
    text: str,
    labels: list[str],
    extra_paths: list[str] | None = None,
) -> list[str]:
    return extract_labeled_paths(
        text,
        labels,
        ["输出要求", "检查要求"],
        extra_paths=extra_paths,
    )


def _extract_scalar(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"^{re.escape(label)}\s*[:：]\s*(.+)$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_section_block(text: str, start_labels: list[str], end_labels: list[str]) -> str:
    return extract_section_block(text, start_labels, end_labels)


def _extract_json_array_paths(block: str) -> list[str]:
    return extract_json_array_paths(block)


def _extract_paths_from_line(line: str) -> list[str]:
    return extract_paths_from_line(line)


def _starts_section(line: str, label: str) -> bool:
    return starts_section(line, label)


def _strip_section_label(line: str) -> str:
    return strip_section_label(line)


def _dedupe(values: list[str]) -> list[str]:
    return dedupe(values)
