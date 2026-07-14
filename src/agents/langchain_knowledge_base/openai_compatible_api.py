from __future__ import annotations

import json
import time
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.knowledge_base.manager import KnowledgeBaseManager, RebuildRequiredError
from src.knowledge_base.schemas import IngestResult, RetrievalResult
from src.knowledge_base.settings import KnowledgeBaseSettings


MODEL_ID = "langchain-knowledge-base-agent"
READINESS_TEXT = "知识库智能体已就绪。请发送需要基于知识库回答的问题。"


class Message(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = MODEL_ID
    messages: list[Message] = Field(default_factory=list)
    stream: bool = False
    top_k: int | None = Field(default=None, ge=1, le=20)
    knowledge_base: str | None = None


class IngestRequest(BaseModel):
    rebuild: bool = False


class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


settings = KnowledgeBaseSettings()
manager = KnowledgeBaseManager(settings.namespace, settings=settings)
app = FastAPI(title="LangChain Knowledge Base Agent", version="1.0.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL_ID,
        "namespace": manager.namespace,
        "embedding_configured": bool(settings.effective_embedding_api_key),
        "chat_configured": bool(settings.openai_api_key),
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "created": 0, "owned_by": "agent-workspace"}]}


@app.get("/v1/knowledge-bases")
def knowledge_bases() -> dict[str, Any]:
    return {"data": [item.model_dump() for item in manager.list_knowledge_bases()]}


@app.post("/v1/knowledge-bases/{name}/ingest", response_model=IngestResult)
def ingest(name: str, request: IngestRequest | None = None) -> IngestResult:
    try:
        return manager.ingest(name, rebuild=request.rebuild if request else False)
    except (ValueError, RebuildRequiredError) as exc:
        raise HTTPException(status_code=409 if isinstance(exc, RebuildRequiredError) else 400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/knowledge-bases/{name}/retrieval", response_model=RetrievalResult)
def retrieve(name: str, request: RetrievalRequest) -> RetrievalResult:
    try:
        return manager.retrieve(name, request.question, top_k=request.top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/chat/completions")
def chat(request: ChatRequest):
    if request.model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"model not found: {request.model}")
    question = _last_user_text(request.messages).strip()
    if not question or question.lower() in {"hello", "hi", "test", "你好", "测试"}:
        content = READINESS_TEXT
    else:
        try:
            result = manager.answer(
                request.knowledge_base or settings.default_name,
                question,
                top_k=request.top_k,
            )
        except FileNotFoundError as exc:
            content = f"知识库尚未入库：{exc}"
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        else:
            content = _render_answer(result.answer, result.citations)
    if request.stream:
        return StreamingResponse(_stream(content, request.model), media_type="text/event-stream")
    return _completion(content, request.model)


def _last_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        if isinstance(message.content, str):
            return message.content
        if isinstance(message.content, list):
            return "\n".join(
                str(part.get("text")) for part in message.content if part.get("type") == "text" and part.get("text")
            )
    return ""


def _render_answer(answer: str, citations: list) -> str:
    if not citations:
        return answer
    sources = "\n".join(f"- {item.source}#chunk-{item.chunk_index}" for item in citations)
    return f"{answer}\n\n来源：\n{sources}"


def _completion(content: str, model: str) -> dict[str, Any]:
    created = int(time.time())
    return {
        "id": f"chatcmpl-kb-{created}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }


def _stream(content: str, model: str) -> Iterable[str]:
    created = int(time.time())
    completion_id = f"chatcmpl-kb-{created}"
    for delta, finish in [({"role": "assistant", "content": content}, None), ({}, "stop")]:
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
