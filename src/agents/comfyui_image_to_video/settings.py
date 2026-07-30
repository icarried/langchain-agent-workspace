from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKFLOW_PATH = Path(__file__).resolve().parent / "assets" / "video_ltx2_3_i2v.json"


class ImageToVideoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        extra="ignore",
    )

    comfyui_i2v_base_url: str = "http://10.180.26.16:8188"
    comfyui_i2v_public_base_url: str | None = None
    comfyui_i2v_workflow_path: Path = DEFAULT_WORKFLOW_PATH
    comfyui_i2v_request_timeout_seconds: float = Field(default=30, gt=0)
    comfyui_i2v_poll_interval_seconds: float = Field(default=2, ge=0.01)
    comfyui_i2v_max_wait_seconds: float = Field(default=1200, gt=0)
    comfyui_i2v_default_size: str = "1280x720"
    comfyui_i2v_default_seconds: int = Field(default=5, ge=1, le=15)
    comfyui_i2v_default_fps: int = Field(default=25, ge=1, le=30)
    comfyui_i2v_max_seconds: int = Field(default=15, ge=1, le=15)
    comfyui_i2v_max_fps: int = Field(default=30, ge=1, le=30)
    comfyui_i2v_allowed_sizes: str = (
        "1280x720,720x1280,1024x1024,1536x864,864x1536,"
        "1920x1080,1080x1920"
    )
    comfyui_i2v_max_input_image_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1024,
    )
    comfyui_i2v_prompt_rewrite_model: str = "qwen3.5-122b-a10b"
    comfyui_i2v_prompt_rewrite_timeout_seconds: float = Field(default=90, gt=0)

    @property
    def allowed_sizes(self) -> tuple[str, ...]:
        return tuple(
            value.strip().lower()
            for value in self.comfyui_i2v_allowed_sizes.split(",")
            if value.strip()
        )

    @property
    def public_base_url(self) -> str:
        return (
            self.comfyui_i2v_public_base_url or self.comfyui_i2v_base_url
        ).rstrip("/")
