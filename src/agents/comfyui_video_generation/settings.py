from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKFLOW_PATH = (
    Path(__file__).resolve().parent / "assets" / "video_ltx2_3_t2v.json"
)


class VideoGenerationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        extra="ignore",
    )

    comfyui_video_base_url: str = "http://10.180.26.16:8188"
    comfyui_video_public_base_url: str | None = None
    comfyui_video_workflow_path: Path = DEFAULT_WORKFLOW_PATH
    comfyui_video_request_timeout_seconds: float = Field(default=30, gt=0)
    comfyui_video_poll_interval_seconds: float = Field(default=2, ge=0.01)
    comfyui_video_max_wait_seconds: float = Field(default=1200, gt=0)
    comfyui_video_default_size: str = "1280x720"
    comfyui_video_default_seconds: int = Field(default=5, ge=1, le=20)
    comfyui_video_default_fps: int = Field(default=25, ge=1, le=60)
    comfyui_video_max_seconds: int = Field(default=20, ge=1, le=120)
    comfyui_video_max_fps: int = Field(default=60, ge=1, le=240)
    comfyui_video_allowed_sizes: str = "1280x720,720x1280"

    @property
    def allowed_sizes(self) -> tuple[str, ...]:
        return tuple(
            value.strip()
            for value in self.comfyui_video_allowed_sizes.split(",")
            if value.strip()
        )

    @property
    def public_base_url(self) -> str:
        return (
            self.comfyui_video_public_base_url or self.comfyui_video_base_url
        ).rstrip("/")
