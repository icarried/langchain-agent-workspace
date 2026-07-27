from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.model_gateway import (
    GPU_STACK_IMAGE_EDIT_MODEL,
    GPU_STACK_IMAGE_MODEL,
    GPU_STACK_VISION_MODEL,
    WORKSPACE_ROOT,
)


class ImageGenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        extra="ignore",
    )

    image_generation_model: str = GPU_STACK_IMAGE_MODEL
    image_edit_model: str = GPU_STACK_IMAGE_EDIT_MODEL
    image_prompt_rewrite_model: str = GPU_STACK_VISION_MODEL
    image_agent_max_input_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    image_agent_timeout_seconds: float = Field(default=300, gt=0)
    image_agent_history_messages: int = Field(default=8, ge=1, le=30)
