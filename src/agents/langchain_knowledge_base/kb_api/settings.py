from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


AGENT_ROOT = Path(__file__).resolve().parent.parent


class KnowledgeBaseConfig(BaseModel):
    name: str
    description: str
    docs_dir: Path
    chroma_collection: str
    chroma_persist_dir: Path | None = None
    keywords: list[str] = Field(default_factory=list)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=AGENT_ROOT / ".env",
        env_prefix="KB_",
        extra="ignore",
    )

    env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8008

    docs_dir: Path = AGENT_ROOT / "data/docs"
    kb_primary_name: str = "primary"
    kb_primary_description: str = "General project and product knowledge base."
    kb_primary_docs_dir: Path = AGENT_ROOT / "data/docs/primary"
    kb_primary_collection: str = "knowledge_base_primary"
    kb_primary_keywords: str = "project,product,docs,general"
    kb_secondary_name: str = "secondary"
    kb_secondary_description: str = "Support, policy, and operations knowledge base."
    kb_secondary_docs_dir: Path = AGENT_ROOT / "data/docs/secondary"
    kb_secondary_collection: str = "knowledge_base_secondary"
    kb_secondary_keywords: str = "support,policy,operations,faq"
    chroma_persist_dir: Path = AGENT_ROOT / "data/chroma"
    chroma_collection: str = "knowledge_base"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-v4"
    top_k: int = Field(default=4, ge=1, le=20)
    min_relevance_score: float = Field(default=0.25, ge=0.0, le=1.0)

    @computed_field
    @property
    def chroma_storage(self) -> str:
        return f"persistent:{self.chroma_persist_dir}"

    @property
    def model_configured(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def embedding_configured(self) -> bool:
        return bool(self.effective_embedding_api_key.strip())

    @property
    def effective_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def effective_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url

    def knowledge_bases(self) -> list[KnowledgeBaseConfig]:
        return [
            KnowledgeBaseConfig(
                name=self.kb_primary_name,
                description=self.kb_primary_description,
                docs_dir=self.kb_primary_docs_dir,
                chroma_collection=self.kb_primary_collection,
                chroma_persist_dir=self.chroma_persist_dir / self.kb_primary_name,
                keywords=_split_keywords(self.kb_primary_keywords),
            ),
            KnowledgeBaseConfig(
                name=self.kb_secondary_name,
                description=self.kb_secondary_description,
                docs_dir=self.kb_secondary_docs_dir,
                chroma_collection=self.kb_secondary_collection,
                chroma_persist_dir=self.chroma_persist_dir / self.kb_secondary_name,
                keywords=_split_keywords(self.kb_secondary_keywords),
            ),
        ]

    def for_knowledge_base(self, kb: KnowledgeBaseConfig) -> "Settings":
        return self.model_copy(
            update={
                "docs_dir": kb.docs_dir,
                "chroma_collection": kb.chroma_collection,
                "chroma_persist_dir": kb.chroma_persist_dir or self.chroma_persist_dir,
            }
        )


def _split_keywords(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
