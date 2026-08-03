from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from src.model_gateway import GPU_STACK_BASE_URL, provider_connection


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    notes: str


MODEL_CONFIGS = {
    "deepseek": ModelConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url=GPU_STACK_BASE_URL,
        api_key_env="DEEPSEEK_API_KEY",
        notes="DeepSeek API 使用 OpenAI-compatible 接口；适合把结构化初筛结果整理为招聘报告。",
    ),
}


def create_chat_model(provider: str = "deepseek", model: str | None = None) -> ChatOpenAI:
    config = MODEL_CONFIGS.get(provider)
    if config is None:
        supported = ", ".join(sorted(MODEL_CONFIGS))
        raise ValueError(f"unsupported provider '{provider}', supported: {supported}")
    connection = provider_connection(
        provider,
        legacy_api_key_env=config.api_key_env,
        default_base_url=config.base_url,
        base_url_override_env="SMART_RESUME_SCREENING_BASE_URL",
    )
    return ChatOpenAI(
        model=model or os.getenv("SMART_RESUME_SCREENING_MODEL") or config.model,
        api_key=connection.api_key,
        base_url=connection.base_url,
        temperature=0,
    )
