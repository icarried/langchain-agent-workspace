from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.agents.openai_compatible_inputs import (
    dedupe,
    extract_json_array_paths,
    extract_labeled_paths,
    extract_paths_from_line,
    messages_to_text_and_urls,
    message_content_to_text_and_urls,
    starts_section,
    strip_section_label,
)

from .service import review_tender_format

MODEL_ID = "tender-format-review-agent"
DEFAULT_REMOTE_TIMEOUT_SECONDS = 30
DEFAULT_MAX_REMOTE_FILE_BYTES = 50 * 1024 * 1024
TEMP_MINIO_SIGNED_NETLOC = "10.71.2.94:9000"
TEMP_MINIO_TRANSPORT_NETLOC = "127.0.0.1:9002"


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


class ParsedTenderReviewRequest(BaseModel):
    docx_input: str
    provider: str
    review_model: str | None = None
    dry_run: bool = False


app = FastAPI(
    title="Tender Format Review OpenAI-compatible API",
    version="0.1.0",
    description="OpenAI-compatible streaming adapter for Dify/FastGPT LLM nodes.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "tender-format-review", "model": MODEL_ID}


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
    parsed = parse_review_request(request)
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


def parse_review_request(
    request: ChatCompletionRequest,
) -> ParsedTenderReviewRequest | None:
    text, content_part_urls = messages_to_text_and_urls(request.messages)
    docx_inputs = _extract_docx_inputs(text, extra_paths=content_part_urls)
    if not docx_inputs:
        return None
    return ParsedTenderReviewRequest(
        docx_input=docx_inputs[0],
        provider=request.provider,
        review_model=request.review_model,
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
    review_request: ParsedTenderReviewRequest,
    model: str,
    *,
    thinking: bool = True,
) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(
        target=_run_review_worker,
        args=(review_request, events),
        daemon=True,
    )
    worker.start()

    yield _sse_delta(completion_id, created, model, "assistant", "")
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        "已接收 1 份招标文件，开始解析与审查。\n\n",
        channel="reasoning_content" if thinking else "content",
    )
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        "正在执行分块审查，请稍候。\n\n",
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
                "审查仍在进行...\n",
                channel="reasoning_content" if thinking else "content",
            )
            continue
        if kind == "result":
            yield _sse_delta(completion_id, created, model, None, payload["report"])
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return
        if kind == "error":
            yield _sse_delta(completion_id, created, model, None, f"审查失败：{payload}\n")
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return


def _run_review_worker(
    review_request: ParsedTenderReviewRequest,
    events: queue.Queue[tuple[str, Any]],
) -> None:
    try:
        events.put(("result", _run_review(review_request)))
    except Exception as exc:  # Surface business errors as model text for LLM clients.
        events.put(("error", str(exc)))


def _run_review(review_request: ParsedTenderReviewRequest) -> dict[str, Any]:
    docx_path, cleanup = _materialize_docx_input(review_request.docx_input)
    try:
        return review_tender_format(
            docx_path,
            provider=review_request.provider,
            model=review_request.review_model,
            dry_run=review_request.dry_run,
        )
    finally:
        if cleanup:
            Path(docx_path).unlink(missing_ok=True)


def _materialize_docx_input(docx_input: str) -> tuple[str, bool]:
    if not _is_http_url(docx_input):
        return docx_input, False

    parsed = urllib.parse.urlparse(docx_input)
    suffix = Path(urllib.parse.unquote(parsed.path)).suffix.lower()
    if suffix != ".docx":
        raise RuntimeError("OpenAI-compatible 入口目前只支持 .docx 招标文件链接。")

    max_bytes = int(os.getenv("TENDER_REVIEW_MAX_REMOTE_FILE_BYTES", DEFAULT_MAX_REMOTE_FILE_BYTES))
    timeout = int(os.getenv("TENDER_REVIEW_REMOTE_TIMEOUT_SECONDS", DEFAULT_REMOTE_TIMEOUT_SECONDS))
    request = _remote_docx_request(docx_input)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise RuntimeError("远程招标文件超过大小上限。")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise RuntimeError("远程招标文件超过大小上限。")

    fd, temp_path = tempfile.mkstemp(prefix="tender-review-", suffix=".docx")
    with os.fdopen(fd, "wb") as file:
        file.write(data)
    return temp_path, True


def _remote_docx_request(docx_input: str) -> urllib.request.Request:
    transport_url, headers = _temporary_minio_transport_mapping(docx_input)
    headers["User-Agent"] = "tender-format-review-agent/0.1"
    return urllib.request.Request(transport_url, headers=headers)


def _temporary_minio_transport_mapping(url: str) -> tuple[str, dict[str, str]]:
    """Route the current FastGPT MinIO URL through localhost without changing Host.

    Temporary deployment workaround: FastGPT emits signed URLs for
    10.71.2.94:9000, but this Windows host reaches that MinIO instance through
    127.0.0.1:9002. AWS V4 signs the Host header, so only the TCP transport
    netloc is changed; the original signed Host is deliberately preserved.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.netloc != TEMP_MINIO_SIGNED_NETLOC:
        return url, {}

    mapped = parsed._replace(netloc=TEMP_MINIO_TRANSPORT_NETLOC)
    return urllib.parse.urlunparse(mapped), {"Host": parsed.netloc}


def _chat_completion_response(
    model: str,
    content: str,
    *,
    created: int | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created or int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


def _readiness_message() -> str:
    return (
        "tender-format-review-agent 已就绪。\n\n"
        "请在正式审查时提供以下格式：\n\n"
        "招标文件：\n"
        "<服务端 .docx 路径或 HTTP(S) .docx 文件链接>\n\n"
        "输出要求：请输出招标文件格式审查报告。\n\n"
        "建议连通性测试先传 dry_run=true；正式审查会调用服务端配置的模型。"
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


def _sse_done(
    completion_id: str,
    created: int,
    model: str,
    *,
    finish_reason: str = "stop",
) -> str:
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


def _extract_docx_inputs(text: str, extra_paths: list[str] | None = None) -> list[str]:
    return extract_labeled_paths(
        text,
        ["招标文件", "待审文件", "文件链接", "文件路径", "附件"],
        ["输出要求", "审查要求"],
        extra_paths=extra_paths,
    )


def _extract_docx_block(text: str) -> str:
    lines: list[str] = []
    collecting = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("-* ")
        if not line:
            continue
        if (
            _starts_section(line, "招标文件")
            or _starts_section(line, "待审文件")
            or _starts_section(line, "文件链接")
            or _starts_section(line, "文件路径")
            or _starts_section(line, "附件")
        ):
            collecting = True
            line = _strip_section_label(line)
        elif _starts_section(line, "输出要求") or _starts_section(line, "审查要求"):
            collecting = False
        if collecting and line:
            lines.append(line)
    return "\n".join(lines)


def _extract_json_array_paths(block: str) -> list[str]:
    return extract_json_array_paths(block)


def _extract_paths_from_line(line: str) -> list[str]:
    return extract_paths_from_line(line)


def _starts_section(line: str, label: str) -> bool:
    return starts_section(line, label)


def _strip_section_label(line: str) -> str:
    return strip_section_label(line)


def _is_http_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _dedupe(values: list[str]) -> list[str]:
    return dedupe(values)
