from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = WORKSPACE_ROOT / "config" / "agent_gateway.json"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    app: str
    upstream: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class McpServerSpec:
    id: str
    upstream: str
    health_upstream: str
    model_id: str | None = None
    enabled: bool = True
    default: bool = False


@dataclass(slots=True)
class ModelStatus:
    healthy: bool = False
    detail: str = "not checked"
    checked_at: float | None = None


@dataclass(slots=True)
class ModelRegistry:
    specs: dict[str, ModelSpec]
    mcp_specs: dict[str, McpServerSpec] = field(default_factory=dict)
    statuses: dict[str, ModelStatus] = field(default_factory=dict)
    mcp_statuses: dict[str, ModelStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for model_id in self.specs:
            self.statuses.setdefault(model_id, ModelStatus())
        for server_id in self.mcp_specs:
            self.mcp_statuses.setdefault(server_id, ModelStatus())
        defaults = [spec.id for spec in self.mcp_specs.values() if spec.default]
        if len(defaults) > 1:
            raise ValueError("only one MCP server may be the default /mcp target")

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ModelRegistry":
        registry_path = Path(path or os.getenv("AGENT_GATEWAY_REGISTRY", DEFAULT_REGISTRY_PATH))
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        overrides = _upstream_overrides()
        mcp_overrides = _mcp_upstream_overrides()
        specs: dict[str, ModelSpec] = {}
        for item in payload.get("models", []):
            spec = ModelSpec(
                id=item["id"],
                app=item["app"],
                upstream=overrides.get(item["id"], item["upstream"]).rstrip("/"),
                enabled=bool(item.get("enabled", True)),
            )
            if spec.id in specs:
                raise ValueError(f"duplicate model id in gateway registry: {spec.id}")
            if spec.enabled:
                specs[spec.id] = spec
        mcp_specs: dict[str, McpServerSpec] = {}
        for item in payload.get("mcp_servers", []):
            upstream = mcp_overrides.get(item["id"], item["upstream"]).rstrip("/")
            spec = McpServerSpec(
                id=item["id"],
                upstream=upstream,
                health_upstream=item.get("health_upstream", upstream.rsplit("/mcp", 1)[0]).rstrip("/"),
                model_id=item.get("model_id"),
                enabled=bool(item.get("enabled", True)),
                default=bool(item.get("default", False)),
            )
            if spec.id in mcp_specs:
                raise ValueError(f"duplicate MCP server id in gateway registry: {spec.id}")
            if spec.enabled:
                mcp_specs[spec.id] = spec
        return cls(specs=specs, mcp_specs=mcp_specs)

    def public_models(self) -> list[dict[str, Any]]:
        return [
            {"id": spec.id, "object": "model", "created": 0, "owned_by": "agent-workspace"}
            for spec in self.specs.values()
            if self.statuses[spec.id].healthy
        ]

    def default_mcp_server(self) -> McpServerSpec | None:
        defaults = [spec for spec in self.mcp_specs.values() if spec.default]
        if defaults:
            return defaults[0]
        if len(self.mcp_specs) == 1:
            return next(iter(self.mcp_specs.values()))
        return None


def _upstream_overrides() -> dict[str, str]:
    raw = os.getenv("AGENT_GATEWAY_UPSTREAM_OVERRIDES", "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError("AGENT_GATEWAY_UPSTREAM_OVERRIDES must be a JSON string map")
    return value


def _mcp_upstream_overrides() -> dict[str, str]:
    raw = os.getenv("AGENT_GATEWAY_MCP_UPSTREAM_OVERRIDES", "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError("AGENT_GATEWAY_MCP_UPSTREAM_OVERRIDES must be a JSON string map")
    return value
