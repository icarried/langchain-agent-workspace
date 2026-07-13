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
from pydantic import BaseModel, ConfigDict, Field

from src.agents.openai_compatible_inputs import (
    dedupe,
    extract_json_array_paths,
    extract_labeled_paths,
    extract_paths_from_line,
    extract_section_block,
    extract_text_before_labeled_section,
    messages_to_text_and_urls,
    message_content_to_text_and_urls,
    starts_section,
    strip_section_label,
)

from .service import screen_resumes

MODEL_ID = "smart-resume-screening-agent"


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


class ParsedScreeningRequest(BaseModel):
    resume_paths: list[str]
    job_description_text: str = ""
    provider: str = "deepseek"
    review_model: str | None = None
    dry_run: bool = False


app = FastAPI(
    title="Smart Resume Screening OpenAI-compatible API",
    version="0.1.0",
    description="OpenAI-compatible streaming adapter for FastGPT/Dify LLM nodes.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "smart-resume-screening", "model": MODEL_ID}


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
    parsed = parse_screening_request(request)
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
    result = _run_screening(parsed)
    return _chat_completion_response(request.model, result["report"], created=started)


def parse_screening_request(request: ChatCompletionRequest) -> ParsedScreeningRequest | None:
    text, content_part_urls = messages_to_text_and_urls(request.messages)
    resume_paths = _extract_resume_paths(text, extra_paths=content_part_urls)
    job_description = _extract_job_description(text)
    if resume_paths and not job_description:
        job_description = _extract_job_description_fallback(text)
    if not resume_paths and not job_description:
        return None
    if not resume_paths:
        return None
    return ParsedScreeningRequest(
        resume_paths=resume_paths,
        job_description_text=job_description,
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
    screening_request: ParsedScreeningRequest,
    model: str,
    *,
    thinking: bool = True,
) -> Generator[str, None, None]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    worker = threading.Thread(target=_run_screening_worker, args=(screening_request, events), daemon=True)
    worker.start()

    yield _sse_delta(completion_id, created, model, "assistant", "")
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        f"已接收 {len(screening_request.resume_paths)} 份简历，开始结构化初筛。\n\n",
        channel="reasoning_content" if thinking else "content",
    )
    for path in screening_request.resume_paths:
        yield _sse_delta(
            completion_id,
            created,
            model,
            None,
            f"准备解析：{path}\n",
            channel="reasoning_content" if thinking else "content",
        )
    yield _sse_delta(
        completion_id,
        created,
        model,
        None,
        "\n正在执行条件匹配、打分和报告整理。\n\n",
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
                "筛选仍在进行...\n",
                channel="reasoning_content" if thinking else "content",
            )
            continue
        if kind == "result":
            yield _sse_delta(completion_id, created, model, None, payload["report"])
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return
        if kind == "error":
            yield _sse_delta(completion_id, created, model, None, f"筛选失败：{payload}\n")
            yield _sse_done(completion_id, created, model)
            yield "data: [DONE]\n\n"
            return


def _run_screening_worker(
    screening_request: ParsedScreeningRequest,
    events: queue.Queue[tuple[str, Any]],
) -> None:
    try:
        events.put(("result", _run_screening(screening_request)))
    except Exception as exc:  # Surface business errors as model text for LLM clients.
        events.put(("error", str(exc)))


def _run_screening(screening_request: ParsedScreeningRequest) -> dict[str, Any]:
    return screen_resumes(
        screening_request.resume_paths,
        job_description_text=screening_request.job_description_text,
        provider=screening_request.provider,
        model=screening_request.review_model,
        dry_run=screening_request.dry_run,
    )


def _chat_completion_response(model: str, content: str, *, created: int | None = None) -> JSONResponse:
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
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


def _readiness_message() -> str:
    return (
        "smart-resume-screening-agent 已就绪。\n\n"
        "请在正式筛选时提供以下格式：\n\n"
        "岗位要求：\n"
        "职位名称：AI 应用开发工程师\n"
        "硬性条件：本科，计算机，Python\n"
        "优先条件：FastAPI，上线\n"
        "淘汰条件：强制通过\n\n"
        "简历文件：\n"
        "<简历文件链接或服务端路径，每行一个>\n\n"
        "输出要求：请输出智能简历筛选排行榜。"
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


def _extract_resume_paths(text: str, extra_paths: list[str] | None = None) -> list[str]:
    return extract_labeled_paths(
        text,
        ["简历文件", "简历路径", "附件"],
        ["岗位要求", "JD", "职位要求", "输出要求"],
        extra_paths=extra_paths,
    )


def _extract_job_description(text: str) -> str:
    return _extract_section_block(
        text,
        ["岗位要求", "JD", "职位要求"],
        ["简历文件", "简历路径", "附件", "输出要求"],
    ).strip()


def _extract_job_description_fallback(text: str) -> str:
    return extract_text_before_labeled_section(
        text,
        ["简历文件", "简历路径", "附件", "输出要求"],
    )


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
