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
from pydantic import BaseModel

from src.agents.openai_compatible import OpenAIChatCompletionRequest, OpenAIChatMessage
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
from src.agents.remote_files import apply_transport_override, materialize_sources

from .service import review_tender_format

MODEL_ID = "tender-format-review-agent"


class ChatMessage(OpenAIChatMessage):
    pass


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID


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
    with materialize_sources(
        [review_request.docx_input],
        allowed_suffixes={".docx"},
        prefix="tender-review-",
    ) as paths:
        return review_tender_format(
            paths[0],
            provider=review_request.provider,
            model=review_request.review_model,
            dry_run=review_request.dry_run,
        )


def _temporary_minio_transport_mapping(url: str) -> tuple[str, dict[str, str]]:
    """Deprecated compatibility alias for the generic transport override."""
    return apply_transport_override(url)


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


def _dedupe(values: list[str]) -> list[str]:
    return dedupe(values)
