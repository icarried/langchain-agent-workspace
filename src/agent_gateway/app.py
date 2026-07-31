from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .registry import ModelRegistry
from .runtime import GatewayRuntime


FORWARDED_REQUEST_HEADERS = {"accept", "content-type", "user-agent", "x-request-id"}
FORWARDED_RESPONSE_HEADERS = {"cache-control", "content-type", "x-accel-buffering", "x-request-id"}
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def create_app(
    registry: ModelRegistry | None = None,
    *,
    runtime: GatewayRuntime | None = None,
    manage_lifespan: bool = True,
) -> FastAPI:
    selected_registry = registry or ModelRegistry.load()
    selected_runtime = runtime or GatewayRuntime(selected_registry)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if manage_lifespan:
            await selected_runtime.start()
        yield
        if manage_lifespan:
            await selected_runtime.close()

    gateway = FastAPI(title="Agent Workspace OpenAI Gateway", version="1.0.0", lifespan=lifespan)
    gateway.state.registry = selected_registry
    gateway.state.runtime = selected_runtime

    @gateway.get("/health")
    async def health() -> dict:
        statuses = selected_registry.statuses
        return {
            "status": "ok",
            "models": {
                model_id: {
                    "healthy": status.healthy,
                    "detail": status.detail,
                    "checked_at": status.checked_at,
                }
                for model_id, status in statuses.items()
            },
            "mcp_servers": {
                server_id: {
                    "healthy": status.healthy,
                    "detail": status.detail,
                    "checked_at": status.checked_at,
                }
                for server_id, status in selected_registry.mcp_statuses.items()
            },
        }

    @gateway.api_route(
        "/mcp",
        methods=["GET", "POST", "DELETE", "OPTIONS"],
    )
    @gateway.api_route(
        "/mcp/{subpath:path}",
        methods=["GET", "POST", "DELETE", "OPTIONS"],
    )
    async def mcp_proxy(request: Request, subpath: str = "") -> Response:
        origin_error = _validate_mcp_origin(request)
        if origin_error:
            return origin_error
        spec = selected_registry.default_mcp_server()
        if spec is None:
            return JSONResponse(
                {"error": "no default MCP server is configured"},
                status_code=503,
            )
        status = selected_registry.mcp_statuses[spec.id]
        if not status.healthy:
            return JSONResponse(
                {"error": "MCP service is temporarily unavailable"},
                status_code=503,
            )
        suffix = f"/{subpath}" if subpath else ""
        query = f"?{request.url.query}" if request.url.query else ""
        upstream_url = f"{spec.upstream}{suffix}{query}"
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
        }
        try:
            upstream_request = selected_runtime.client.build_request(
                request.method,
                upstream_url,
                content=await request.body(),
                headers=headers,
            )
            upstream = await selected_runtime.client.send(upstream_request, stream=True)
        except (httpx.HTTPError, OSError) as exc:
            selected_runtime.mark_mcp_unhealthy(spec.id, exc)
            return JSONResponse(
                {"error": "MCP service is temporarily unavailable"},
                status_code=503,
            )

        response_headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
        }

        async def proxy_body() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            except (httpx.HTTPError, OSError) as exc:
                selected_runtime.mark_mcp_unhealthy(spec.id, exc)
            finally:
                await upstream.aclose()

        return StreamingResponse(
            proxy_body(),
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=None,
        )

    @gateway.get("/v1/models")
    async def models(request: Request) -> Response:
        auth_error = _authorize(request)
        if auth_error:
            return auth_error
        return JSONResponse({"object": "list", "data": selected_registry.public_models()})

    @gateway.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        auth_error = _authorize(request)
        if auth_error:
            return auth_error
        raw_body = await request.body()
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _openai_error(400, "invalid JSON request body", "invalid_request_error")
        if not isinstance(payload, dict) or not isinstance(payload.get("model"), str):
            return _openai_error(400, "model is required", "invalid_request_error", param="model")
        model_id = payload["model"]
        spec = selected_registry.specs.get(model_id)
        if spec is None:
            return _openai_error(404, f"model not found: {model_id}", "model_not_found", code="model_not_found")
        if not selected_registry.statuses[model_id].healthy:
            return _openai_error(503, f"model is temporarily unavailable: {model_id}", "server_error", code="model_unavailable")

        upstream_headers = {
            key: value for key, value in request.headers.items() if key.lower() in FORWARDED_REQUEST_HEADERS
        }
        upstream_url = f"{spec.upstream}/v1/chat/completions"
        try:
            upstream_request = selected_runtime.client.build_request(
                "POST", upstream_url, content=raw_body, headers=upstream_headers
            )
            upstream = await selected_runtime.client.send(upstream_request, stream=True)
        except (httpx.HTTPError, OSError) as exc:
            selected_runtime.mark_unhealthy(model_id, exc)
            return _openai_error(503, f"model is temporarily unavailable: {model_id}", "server_error", code="model_unavailable")

        response_headers = {
            key: value for key, value in upstream.headers.items() if key.lower() in FORWARDED_RESPONSE_HEADERS
        }
        if not payload.get("stream", False):
            try:
                body = await upstream.aread()
            except httpx.HTTPError as exc:
                selected_runtime.mark_unhealthy(model_id, exc)
                await upstream.aclose()
                return _openai_error(503, f"model response failed: {model_id}", "server_error", code="upstream_failure")
            await upstream.aclose()
            return Response(body, status_code=upstream.status_code, headers=response_headers)

        async def stream_body() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            except (httpx.HTTPError, OSError) as exc:
                selected_runtime.mark_unhealthy(model_id, exc)
                error = {"error": {"message": "upstream stream interrupted", "type": "server_error", "code": "upstream_failure"}}
                yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            finally:
                await upstream.aclose()

        return StreamingResponse(
            stream_body(),
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=upstream.headers.get("content-type", "text/event-stream").split(";", 1)[0],
        )

    return gateway


def _authorize(request: Request) -> JSONResponse | None:
    required = os.getenv("AGENT_GATEWAY_API_KEY", "")
    if not required:
        return None
    if request.headers.get("authorization") != f"Bearer {required}":
        return _openai_error(401, "invalid API key", "authentication_error", code="invalid_api_key")
    return None


def _validate_mcp_origin(request: Request) -> JSONResponse | None:
    origin = request.headers.get("origin")
    if not origin:
        return None
    allowed = {
        item.strip()
        for item in os.getenv("AGENT_MCP_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin not in allowed:
        return JSONResponse({"error": "MCP origin is not allowed"}, status_code=403)
    return None


def _openai_error(
    status_code: int,
    message: str,
    error_type: str,
    *,
    param: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": error_type, "param": param, "code": code}},
        status_code=status_code,
    )


app = create_app()
