from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


GPU_STACK_BASE_URL = "http://10.100.5.33:8003/v1"


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
        base_url=GPU_STACK_BASE_URL,
        api_key_env="DEEPSEEK_API_KEY",
        practical_chunk_chars=12000,
        notes="候选人片段并行审查，候选人级决策后再执行确定性筛除和排序。",
    ),
    "dashscope": ModelConfig(
        provider="dashscope",
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        practical_chunk_chars=12000,
        notes="通过 DashScope OpenAI-compatible 接口调用 Qwen。",
    ),
}


def create_chat_model(provider: str = "deepseek", model: str | None = None) -> ChatOpenAI:
    load_dotenv(Path.cwd() / ".env.local")
    config = MODEL_CONFIGS.get(provider)
    if config is None:
        supported = ", ".join(sorted(MODEL_CONFIGS))
        raise ValueError(f"unsupported provider '{provider}', supported: {supported}")

    if provider == "deepseek":
        api_key = os.getenv("GPU_STACK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        base_url = (
            os.getenv("BATCH_RESUME_REVIEW_BASE_URL")
            or os.getenv("GPU_STACK_BASE_URL")
            or config.base_url
        )
        key_name = "GPU_STACK_API_KEY"
    else:
        api_key = os.getenv(config.api_key_env)
        base_url = os.getenv("BATCH_RESUME_REVIEW_BASE_URL") or config.base_url
        key_name = config.api_key_env
    if not api_key:
        raise RuntimeError(f"missing {key_name}; set it in .env.local")
    if not api_key.isascii() or any(char.isspace() for char in api_key):
        raise RuntimeError(f"{key_name} must be a plain ASCII token without whitespace")

    return ChatOpenAI(
        model=model or os.getenv("BATCH_RESUME_REVIEW_MODEL") or config.model,
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        temperature=0,
    )
