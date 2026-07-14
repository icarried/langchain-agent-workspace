from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


class KnowledgeBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        env_prefix="KB_",
        extra="ignore",
    )

    data_root: Path = WORKSPACE_ROOT / "data" / "knowledge_bases"
    namespace: str = "langchain-knowledge-base-agent"
    default_name: str = "default"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-v4"
    top_k: int = Field(default=4, ge=1, le=20)
    min_relevance_score: float = Field(default=0.25, ge=0, le=1)

    @property
    def effective_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def effective_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url
