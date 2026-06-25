from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    practical_chunk_chars: int
    notes: str


MODEL_CONFIGS = {
    "deepseek": ModelConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        practical_chunk_chars=16000,
        notes="DeepSeek API 使用 OpenAI-compatible 接口；按小块审查可降低遗漏率并便于失败重试。",
    ),
    "dashscope": ModelConfig(
        provider="dashscope",
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        practical_chunk_chars=16000,
        notes="DashScope 使用 OpenAI 兼容模式接入 Qwen；具体上下文上限随 qwen-plus/max/long 等模型变化，运行前应核对官方模型页。",
    ),
}


def create_chat_model(provider: str = "deepseek", model: str | None = None) -> ChatOpenAI:
    load_dotenv(Path.cwd() / ".env.local")
    config = MODEL_CONFIGS.get(provider)
    if config is None:
        supported = ", ".join(sorted(MODEL_CONFIGS))
        raise ValueError(f"unsupported provider '{provider}', supported: {supported}")

    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise RuntimeError(f"missing {config.api_key_env}; set it in .env.local")
    if not api_key.isascii() or any(char.isspace() for char in api_key):
        raise RuntimeError(
            f"{config.api_key_env} does not look like a valid API key; "
            "it must be a plain ASCII token without whitespace. Check .env.local."
        )

    return ChatOpenAI(
        model=model or os.getenv("TENDER_REVIEW_MODEL") or config.model,
        api_key=api_key,
        base_url=os.getenv("TENDER_REVIEW_BASE_URL") or config.base_url,
        temperature=0,
    )
