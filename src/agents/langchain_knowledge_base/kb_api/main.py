import json
import time
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from kb_api.rag.answer import RagAnswerService, build_citations
from kb_api.rag.ingest import IngestService
from kb_api.rag.retriever import RagRetriever
from kb_api.router import KnowledgeBaseRouter
from kb_api.schemas import ComponentHealth, HealthResponse, HealthStatus
from kb_api.schemas import ChatCompletionsRequest, ChatResponse, IngestRequest, IngestResponse
from kb_api.schemas import RetrievalRequest, RetrievalResponse
from kb_api.settings import Settings
from kb_api.settings import get_settings

app = FastAPI(title="LangChain Knowledge Base API", version="0.1.0")
MODEL_ID = "langchain-knowledge-base-agent"
READINESS_TEXT = (
    "Knowledge base agent is ready. Put documents under data/docs, call POST /ingest, "
    "then ask questions with POST /v1/chat/completions. Use POST /v1/retrieval for evidence-only retrieval."
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    docs_detail = f"docs={settings.docs_dir}"
    model_ready = settings.model_configured and settings.embedding_configured
    model_status = HealthStatus.ok if model_ready else HealthStatus.missing_config
    missing = []
    if not settings.model_configured:
        missing.append("KB_OPENAI_API_KEY")
    if not settings.embedding_configured:
        missing.append("KB_EMBEDDING_API_KEY or KB_OPENAI_API_KEY")
    model_detail = None if model_ready else f"{', '.join(missing)} is not configured"

    return HealthResponse(
        api=ComponentHealth(status=HealthStatus.ok, detail=docs_detail),
        chroma=ComponentHealth(status=HealthStatus.ok, detail=settings.chroma_storage),
        model=ComponentHealth(status=model_status, detail=model_detail),
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest | None = None) -> IngestResponse:
    settings = get_settings()
    if not settings.embedding_configured:
        raise HTTPException(status_code=503, detail="KB_EMBEDDING_API_KEY or KB_OPENAI_API_KEY is not configured")

    try:
        routed_settings = route_settings(settings, request.knowledge_base if request else None)
        service = build_ingest_service(routed_settings)
        return service.ingest(docs_dir=request.docs_dir if request else None).to_response()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/retrieval", response_model=RetrievalResponse)
def retrieve(request: RetrievalRequest) -> RetrievalResponse:
    settings = get_settings()
    if not settings.embedding_configured:
        raise HTTPException(status_code=503, detail="KB_EMBEDDING_API_KEY or KB_OPENAI_API_KEY is not configured")

    try:
        routed_settings = route_settings(settings, request.knowledge_base)
        retriever = build_retrieval_service(routed_settings)
        chunks = retriever.retrieve(request.question, top_k=request.top_k)
        citations = build_citations(chunks)
        return RetrievalResponse(query=request.question, citations=citations, refused=not bool(citations))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "created": 0, "owned_by": "local"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionsRequest):
    question = _last_user_text(request.messages).strip()
    if not question:
        content = READINESS_TEXT
    else:
        response = answer_question(
            question,
            top_k=request.top_k,
            knowledge_base=request.knowledge_base,
        )
        content = render_answer_with_sources(response)

    if request.stream:
        return StreamingResponse(_stream_completion(content, request.model), media_type="text/event-stream")
    return _completion(content, request.model)


def route_settings(settings: Settings, knowledge_base: str | None) -> Settings:
    if not knowledge_base:
        return settings
    router = KnowledgeBaseRouter(settings)
    decision = router.route("", requested_name=knowledge_base)
    return settings.for_knowledge_base(router.selected_config(decision))


def build_ingest_service(settings: Settings) -> IngestService:
    return IngestService(settings)


def build_retrieval_service(settings: Settings) -> RagRetriever:
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.effective_embedding_api_key,
        base_url=settings.effective_embedding_base_url,
        tiktoken_enabled=False,
        check_embedding_ctx_length=False,
    )
    vectorstore = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(settings.chroma_persist_dir),
        embedding_function=embeddings,
    )
    return RagRetriever(vectorstore, settings=settings)


def build_answer_service(settings: Settings) -> RagAnswerService:
    from langchain_openai import ChatOpenAI

    chat_model = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0,
    )
    return RagAnswerService(
        retriever=build_retrieval_service(settings),
        chat_model=chat_model,
        settings=settings,
    )


def answer_question(question: str, *, top_k: int | None, knowledge_base: str | None) -> ChatResponse:
    settings = get_settings()
    if not settings.model_configured:
        raise HTTPException(status_code=503, detail="KB_OPENAI_API_KEY is not configured")
    if not settings.embedding_configured:
        raise HTTPException(status_code=503, detail="KB_EMBEDDING_API_KEY or KB_OPENAI_API_KEY is not configured")

    try:
        routed_settings = route_settings(settings, knowledge_base)
        service = build_answer_service(routed_settings)
        return service.answer(question, top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def render_answer_with_sources(response: ChatResponse) -> str:
    if not response.citations:
        return response.answer

    sources = "\n".join(f"- {citation.source}#chunk-{citation.chunk_index}" for citation in response.citations)
    return f"{response.answer}\n\n来源：\n{sources}"


def _last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return _flatten_content(message.content)
    return ""


def _flatten_content(content: str | list[dict[str, Any]] | None) -> str:
    if isinstance(content, str):
        return content
    if not content:
        return ""

    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def _completion(content: str, model: str) -> dict[str, Any]:
    created = int(time.time())
    return {
        "id": f"chatcmpl-kb-{created}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


def _stream_completion(content: str, model: str) -> Iterable[str]:
    created = int(time.time())
    chunk = {
        "id": f"chatcmpl-kb-{created}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    stop = {
        "id": f"chatcmpl-kb-{created}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(stop, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
