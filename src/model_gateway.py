"""Shared OpenAI-compatible GPU Stack configuration."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
GPU_STACK_BASE_URL = "http://10.100.5.33:8003/v1"
GPU_STACK_DEEPSEEK_MODEL = "deepseek-v4-flash"
GPU_STACK_VISION_MODEL = "qwen3.6-35b-a3b"
GPU_STACK_EMBEDDING_MODEL = "qwen3-vl-embedding-8b"
GPU_STACK_IMAGE_MODEL = "z-image-turbo"
GPU_STACK_IMAGE_EDIT_MODEL = "qwen-image-edit"
GPU_STACK_OCR_MODEL = "paddleocr-vl-1.6"


@dataclass(frozen=True, slots=True)
class OpenAIConnection:
    api_key: str
    base_url: str
    api_key_source: str


def load_workspace_env() -> None:
    load_dotenv(WORKSPACE_ROOT / ".env.local")


def gpu_stack_connection() -> OpenAIConnection:
    load_workspace_env()
    api_key = os.getenv("GPU_STACK_API_KEY", "").strip()
    source = "GPU_STACK_API_KEY"
    if not api_key:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        source = "DEEPSEEK_API_KEY"
        if api_key:
            warnings.warn(
                "DEEPSEEK_API_KEY is deprecated for GPU Stack; use GPU_STACK_API_KEY",
                DeprecationWarning,
                stacklevel=2,
            )
    validate_api_key(api_key, source)
    return OpenAIConnection(
        api_key=api_key,
        base_url=os.getenv("GPU_STACK_BASE_URL", GPU_STACK_BASE_URL).rstrip("/"),
        api_key_source=source,
    )


def provider_connection(
    provider: str,
    *,
    legacy_api_key_env: str,
    default_base_url: str,
    base_url_override_env: str,
) -> OpenAIConnection:
    load_workspace_env()
    explicit_base_url = os.getenv(base_url_override_env, "").strip()
    if provider == "deepseek":
        shared = gpu_stack_connection()
        return OpenAIConnection(
            api_key=shared.api_key,
            base_url=(explicit_base_url or shared.base_url).rstrip("/"),
            api_key_source=shared.api_key_source,
        )

    api_key = os.getenv(legacy_api_key_env, "").strip()
    validate_api_key(api_key, legacy_api_key_env)
    return OpenAIConnection(
        api_key=api_key,
        base_url=(explicit_base_url or default_base_url).rstrip("/"),
        api_key_source=legacy_api_key_env,
    )


def validate_api_key(api_key: str, source: str) -> None:
    if not api_key:
        raise RuntimeError(f"missing {source}; set it in .env.local")
    if not api_key.isascii() or any(char.isspace() for char in api_key):
        raise RuntimeError(f"{source} must be a plain ASCII token without whitespace")
