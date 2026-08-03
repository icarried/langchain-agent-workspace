from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = WORKSPACE_ROOT / "config" / "agent_gateway.json"


@dataclass(frozen=True, slots=True)
class McpBackendSpec:
    id: str
    upstream: str
    prefix: str | None = None
    tool_names: dict[str, str] | None = None
    enabled: bool = True


def load_mcp_backends(path: str | Path | None = None) -> list[McpBackendSpec]:
    registry_path = Path(
        path or os.getenv("AGENT_GATEWAY_REGISTRY", DEFAULT_REGISTRY_PATH)
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    overrides = _upstream_overrides()
    backends: list[McpBackendSpec] = []
    ids: set[str] = set()
    prefixes: set[str] = set()
    for item in payload.get("mcp_backends", []):
        spec = McpBackendSpec(
            id=item["id"],
            upstream=overrides.get(item["id"], item["upstream"]).rstrip("/"),
            prefix=item.get("prefix") or None,
            tool_names=item.get("tool_names") or None,
            enabled=bool(item.get("enabled", True)),
        )
        if spec.tool_names is not None and (
            not isinstance(spec.tool_names, dict)
            or not all(
                isinstance(source, str) and isinstance(target, str)
                for source, target in spec.tool_names.items()
            )
        ):
            raise ValueError(f"invalid MCP tool name map for backend: {spec.id}")
        if spec.id in ids:
            raise ValueError(f"duplicate MCP backend id: {spec.id}")
        if spec.prefix and spec.prefix in prefixes:
            raise ValueError(f"duplicate MCP backend prefix: {spec.prefix}")
        ids.add(spec.id)
        if spec.prefix:
            prefixes.add(spec.prefix)
        if spec.enabled:
            backends.append(spec)
    if not backends:
        raise ValueError("at least one enabled MCP backend is required")
    return backends


def _upstream_overrides() -> dict[str, str]:
    raw = os.getenv("AGENT_GATEWAY_MCP_BACKEND_OVERRIDES", "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(upstream, str)
        for key, upstream in value.items()
    ):
        raise ValueError("AGENT_GATEWAY_MCP_BACKEND_OVERRIDES must be a JSON string map")
    return value
