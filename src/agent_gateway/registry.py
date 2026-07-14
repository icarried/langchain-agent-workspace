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


@dataclass(slots=True)
class ModelStatus:
    healthy: bool = False
    detail: str = "not checked"
    checked_at: float | None = None


@dataclass(slots=True)
class ModelRegistry:
    specs: dict[str, ModelSpec]
    statuses: dict[str, ModelStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for model_id in self.specs:
            self.statuses.setdefault(model_id, ModelStatus())

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ModelRegistry":
        registry_path = Path(path or os.getenv("AGENT_GATEWAY_REGISTRY", DEFAULT_REGISTRY_PATH))
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        overrides = _upstream_overrides()
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
        return cls(specs=specs)

    def public_models(self) -> list[dict[str, Any]]:
        return [
            {"id": spec.id, "object": "model", "created": 0, "owned_by": "agent-workspace"}
            for spec in self.specs.values()
            if self.statuses[spec.id].healthy
        ]


def _upstream_overrides() -> dict[str, str]:
    raw = os.getenv("AGENT_GATEWAY_UPSTREAM_OVERRIDES", "").strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError("AGENT_GATEWAY_UPSTREAM_OVERRIDES must be a JSON string map")
    return value
