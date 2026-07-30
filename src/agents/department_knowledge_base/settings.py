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
    max_files_per_request: int = Field(default=100, ge=1, le=500)
    max_file_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_batch_bytes: int = Field(default=500 * 1024 * 1024, ge=1)
    max_batch_ocr_pages: int = Field(default=1000, ge=1, le=10000)
    doc_conversion_timeout_seconds: float = Field(default=60, gt=0, le=600)
    query_rewrite_enabled: bool = True
    query_rewrite_model: str = "deepseek-v4-flash"
    query_rewrite_timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_rewritten_queries: int = Field(default=5, ge=1, le=10)
    retrieval_top_k_per_query: int = Field(default=5, ge=1, le=20)
    max_context_chunks: int = Field(default=20, ge=1, le=100)
    max_source_documents: int = Field(default=10, ge=1, le=10)
    max_download_files: int = Field(default=10, ge=1, le=10)
    max_download_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_download_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    import_task_workers: int = Field(default=2, ge=1, le=16)
    import_task_retention_days: int = Field(default=30, ge=1, le=365)
    stream_heartbeat_seconds: float = Field(default=10, gt=0, le=60)
    allow_local_files: bool = False
    object_store_enabled: bool = False
    minio_endpoint: str = "department-kb-minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
