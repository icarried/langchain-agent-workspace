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
from src.agents.openai_compatible import OpenAIChatCompletionRequest, OpenAIChatMessage
from src.agents.openai_compatible_inputs import (
    dedupe,
    extract_json_array_paths,
    extract_labeled_paths,
    extract_paths_from_line,
    extract_text_before_labeled_section,
    messages_to_text_and_urls,
    message_content_to_text_and_urls,
    starts_section,
    strip_section_label,
)

from .api import BatchResumeReviewRequest, review
from .mcp_server import mcp

MODEL_ID = "batch-resume-review-agent"


class ChatMessage(OpenAIChatMessage):
    pass


class ChatCompletionRequest(OpenAIChatCompletionRequest):
    model: str = MODEL_ID


mcp_http_app = mcp.http_app(path="/", stateless_http=True)
app = FastAPI(
    title="Batch Resume Review OpenAI-compatible API",
    version="0.1.0",
    description="OpenAI-compatible streaming adapter for Dify/FastGPT LLM nodes.",
    lifespan=mcp_http_app.lifespan,
)
app.mount("/mcp", mcp_http_app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "batch-resume-review-llm", "model": MODEL_ID}


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
    result = review(parsed)
    content = result["report"]
    return _chat_completion_response(request.model, content, created=started)


def parse_review_request(request: ChatCompletionRequest) -> BatchResumeReviewRequest | None:
    text, content_part_urls = messages_to_text_and_urls(request.messages)
    resume_paths = _extract_resume_paths(text, extra_paths=content_part_urls)
    job_description = _extract_job_description(text)
    if resume_paths and not job_description:
        job_description = _extract_job_description_fallback(text)
    if not resume_paths and not job_description:
        return None
    if not resume_paths or not job_description:
        return None
    return BatchResumeReviewRequest(
        resume_paths=resume_paths,
        job_description_text=job_description,
        provider=request.provider,
        model=request.review_model,
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
    review_request: BatchResumeReviewRequest,
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
        f"已接收 {len(review_request.resume_paths)} 份简历，开始解析与审查。\n\n",
        channel="reasoning_content" if thinking else "content",
    )
    for path in review_request.resume_paths:
        yield _sse_delta(
            completion_id,
            created,
            model,
            None,
            f"准备审查：{path}\n",
            channel="reasoning_content" if thinking else "content",
        )
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        "\n正在执行两阶段审查，请稍候。\n\n",
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
            yield _sse_delta(
                completion_id,
                created,
                model,
                None,
                f"审查失败：{payload}\n",
            )
            yield _sse_done(completion_id, created, model, finish_reason="stop")
            yield "data: [DONE]\n\n"
            return


def _run_review_worker(
    review_request: BatchResumeReviewRequest,
    events: queue.Queue[tuple[str, Any]],
) -> None:
    try:
        events.put(("result", review(review_request)))
    except Exception as exc:  # Surface errors as model text for LLM clients.
        events.put(("error", str(exc)))


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
        "batch-resume-review-agent 已就绪。\n\n"
        "请在正式审查时提供以下格式：\n\n"
        "岗位要求：<岗位 JD 文本>\n\n"
        "简历文件：\n"
        "<简历文件链接或服务端路径，每行一个>\n\n"
        "支持 PDF、DOC、DOCX、MD、TXT；FastGPT 的文件链接数组可渲染为多行 URL。"
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


def _extract_resume_paths(text: str, extra_paths: list[str] | None = None) -> list[str]:
    return extract_labeled_paths(
        text,
        ["简历文件", "简历路径", "附件"],
        ["岗位要求", "JD", "职位要求", "输出要求"],
        extra_paths=extra_paths,
    )


def _extract_resume_block(text: str) -> str:
    lines: list[str] = []
    collecting = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("-* ")
        if not line:
            continue
        if (
            _starts_section(line, "简历文件")
            or _starts_section(line, "简历路径")
            or _starts_section(line, "附件")
        ):
            collecting = True
            line = _strip_section_label(line)
        elif (
            _starts_section(line, "岗位要求")
            or _starts_section(line, "JD")
            or _starts_section(line, "职位要求")
            or _starts_section(line, "输出要求")
        ):
            collecting = False
        if collecting and line:
            lines.append(line)
    return "\n".join(lines)


def _extract_json_array_paths(block: str) -> list[str]:
    return extract_json_array_paths(block)


def _extract_paths_from_line(line: str) -> list[str]:
    return extract_paths_from_line(line)


def _extract_job_description(text: str) -> str:
    lines: list[str] = []
    collecting = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if _starts_section(line, "岗位要求") or _starts_section(line, "JD"):
            collecting = True
            line = _strip_section_label(line)
            if line:
                lines.append(line)
            continue
        if collecting and (
            _starts_section(line, "简历文件")
            or _starts_section(line, "简历路径")
            or _starts_section(line, "附件")
            or _starts_section(line, "输出要求")
        ):
            break
        if collecting:
            lines.append(line)
    return "\n".join(lines).strip()


def _extract_job_description_fallback(text: str) -> str:
    return extract_text_before_labeled_section(
        text,
        ["简历文件", "简历路径", "附件", "输出要求"],
    )


def _starts_section(line: str, label: str) -> bool:
    return starts_section(line, label)


def _strip_section_label(line: str) -> str:
    return strip_section_label(line)


def _dedupe(values: list[str]) -> list[str]:
    return dedupe(values)
