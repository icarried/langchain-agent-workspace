from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.knowledge_base.settings import WORKSPACE_ROOT
from src.model_gateway import GPU_STACK_OCR_MODEL, GPU_STACK_VISION_MODEL


class DepartmentKnowledgeBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        env_prefix="DEPARTMENT_KB_",
        extra="ignore",
    )

    intent_model: str = GPU_STACK_VISION_MODEL
    intent_timeout_seconds: float = Field(default=60, gt=0, le=600)
    ocr_model: str = GPU_STACK_OCR_MODEL
    ocr_timeout_seconds: float = Field(default=180, gt=0, le=1200)
    ocr_max_pages: int = Field(default=100, ge=1, le=1000)
    min_local_text_chars: int = Field(default=20, ge=0, le=10000)
    max_files_per_request: int = Field(default=20, ge=1, le=100)
    allow_local_files: bool = False
    object_store_enabled: bool = False
    minio_endpoint: str = "department-kb-minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
