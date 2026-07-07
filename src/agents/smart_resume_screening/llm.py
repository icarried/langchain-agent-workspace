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
    notes: str


MODEL_CONFIGS = {
    "deepseek": ModelConfig(
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        notes="DeepSeek API 使用 OpenAI-compatible 接口；适合把结构化初筛结果整理为招聘报告。",
    ),
    "dashscope": ModelConfig(
        provider="dashscope",
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        notes="DashScope 使用 OpenAI 兼容模式接入 Qwen；正式运行前应确认模型上下文和价格。",
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
        raise RuntimeError(f"{config.api_key_env} must be a plain ASCII token without whitespace.")
    return ChatOpenAI(
        model=model or os.getenv("SMART_RESUME_SCREENING_MODEL") or config.model,
        api_key=api_key,
        base_url=os.getenv("SMART_RESUME_SCREENING_BASE_URL") or config.base_url,
        temperature=0,
    )

