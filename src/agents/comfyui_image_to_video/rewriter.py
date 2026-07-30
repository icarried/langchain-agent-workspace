from __future__ import annotations

from typing import Any, Protocol

import httpx

from src.agents.image_generation.client import (
    extract_text_content,
    parse_rewritten_prompt,
)
from src.model_gateway import gpu_stack_connection

from .prompts import SYSTEM_PROMPT, user_prompt
from .settings import ImageToVideoSettings


class PromptRewriteError(RuntimeError):
    """Sanitized prompt rewrite failure."""


class PromptRewriter(Protocol):
    async def rewrite(
        self,
        *,
        instruction: str,
        history: str,
        image_data_url: str,
        size: str,
        seconds: int,
        fps: int,
    ) -> str: ...


class GPUStackPromptRewriter:
    def __init__(
        self,
        settings: ImageToVideoSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    async def rewrite(
        self,
        *,
        instruction: str,
        history: str,
        image_data_url: str,
        size: str,
        seconds: int,
        fps: int,
    ) -> str:
        try:
            connection = gpu_stack_connection()
        except RuntimeError as exc:
            raise PromptRewriteError("GPU Stack API Key未配置") from exc
        if not connection.api_key:
            raise PromptRewriteError("GPU Stack API Key未配置")
        payload: dict[str, Any] = {
            "model": self.settings.comfyui_i2v_prompt_rewrite_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt(
                                instruction,
                                history,
                                size=size,
                                seconds=seconds,
                                fps=fps,
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        headers = {
            "Authorization": f"Bearer {connection.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.comfyui_i2v_prompt_rewrite_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    f"{connection.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise PromptRewriteError("提示词改写超时") from exc
        except httpx.HTTPError as exc:
            raise PromptRewriteError("提示词改写服务连接失败") from exc
        if response.status_code >= 400:
            raise PromptRewriteError(
                f"提示词改写失败（HTTP {response.status_code}）"
            )
        try:
            value = response.json()
            return parse_rewritten_prompt(extract_text_content(value))
        except (ValueError, RuntimeError) as exc:
            raise PromptRewriteError("提示词改写响应格式无效") from exc
