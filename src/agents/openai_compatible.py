"""Shared protocol models and response helpers for agent model adapters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OpenAIChatMessage(BaseModel):
    role: str
    content: Any


class OpenAIChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[OpenAIChatMessage] = Field(default_factory=list)
    stream: bool = False
    provider: str = "deepseek"
    review_model: str | None = None
    dry_run: bool = False
    thinking: bool = True


def model_list(model_id: str) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": "agent-workspace",
            }
        ],
    }
