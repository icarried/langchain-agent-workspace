from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Any

from fastapi import FastAPI
from fastmcp import FastMCP

from .registry import McpBackendSpec, load_mcp_backends


ProxyFactory = Callable[[str], FastMCP[Any]]


def build_mcp_gateway(
    backends: list[McpBackendSpec],
    *,
    proxy_factory: ProxyFactory | None = None,
) -> FastMCP:
    create_proxy = proxy_factory or _create_proxy
    gateway = FastMCP(
        "Agent Workspace MCP Gateway",
        instructions=(
            "Unified access to independently deployed workspace agents. Tool prefixes "
            "are stable public API namespaces; use tools/list to discover capabilities."
        ),
        mask_error_details=True,
    )
    for backend in backends:
        proxy = create_proxy(backend.upstream)
        _mount_backend(gateway, proxy, backend)
    return gateway


def _create_proxy(upstream: str) -> FastMCP[Any]:
    try:
        from fastmcp.server import create_proxy
    except ImportError:  # FastMCP 2.x compatibility
        return FastMCP.as_proxy(upstream)
    return create_proxy(upstream)


def _mount_backend(
    gateway: FastMCP[Any],
    proxy: FastMCP[Any],
    backend: McpBackendSpec,
) -> None:
    parameters = inspect.signature(FastMCP.mount).parameters
    if "namespace" in parameters:
        gateway.mount(
            proxy,
            namespace=backend.prefix,
            tool_names=backend.tool_names,
        )
    else:
        tool_names = backend.tool_names
        if backend.prefix and tool_names:
            # FastMCP 2.x treats an explicit tool rename as the final public name
            # instead of applying the mount prefix after the rename.
            tool_names = {
                source: f"{backend.prefix}_{target}"
                for source, target in tool_names.items()
            }
        gateway.mount(
            proxy,
            prefix=backend.prefix,
            tool_names=tool_names,
        )


def create_app(backends: list[McpBackendSpec] | None = None) -> FastAPI:
    selected = backends or load_mcp_backends()
    mcp = build_mcp_gateway(selected)
    mcp_http_app = mcp.http_app(path="/", stateless_http=True)
    application = FastAPI(
        title="Agent Workspace MCP Gateway",
        version="1.0.0",
        lifespan=mcp_http_app.lifespan,
    )

    @application.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "backends": [
                {
                    "id": backend.id,
                    "prefix": backend.prefix,
                    "tool_names": backend.tool_names,
                    "upstream": backend.upstream,
                }
                for backend in selected
            ],
        }

    application.mount("/mcp", mcp_http_app)
    return application


app = create_app()
