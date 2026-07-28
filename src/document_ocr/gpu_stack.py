from __future__ import annotations

import base64
from typing import Any

import httpx

from src.model_gateway import GPU_STACK_OCR_MODEL, gpu_stack_connection


DEFAULT_MODEL = GPU_STACK_OCR_MODEL
DEFAULT_TIMEOUT_SECONDS = 180.0
OCR_PROMPT = (
    "请将这张文档页面解析为结构化 Markdown。逐字保留可见文字、标题、段落、列表、"
    "表格和公式的阅读顺序；不要总结、改写、补全或猜测。无法辨认的内容标记为 [?]。"
    "只返回解析后的 Markdown 正文。"
)


class OCRRequestError(RuntimeError):
    """A sanitized OCR provider failure."""


class GPUStackPaddleOCRVL:
    """OpenAI-compatible PaddleOCR-VL provider hosted by GPU Stack.

    The provider deliberately handles one rendered page/image per request. It is
    replaceable so a future official full PaddleOCR-VL pipeline service can be
    integrated without changing knowledge-base ingestion.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("OCR timeout must be positive")
        if base_url is None or api_key is None:
            connection = gpu_stack_connection()
            base_url = base_url or connection.base_url
            api_key = api_key or connection.api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport

    def extract_image(self, data: bytes, mime_type: str, *, source: str) -> str:
        if not data:
            raise ValueError(f"OCR input is empty for {source!r}")
        encoded = base64.b64encode(data).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded}",
                            },
                        },
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
            "stream": False,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise OCRRequestError("PaddleOCR-VL request timed out") from exc
        except httpx.HTTPError as exc:
            raise OCRRequestError("PaddleOCR-VL connection failed") from exc
        if response.status_code >= 400:
            raise OCRRequestError(
                f"PaddleOCR-VL request failed (HTTP {response.status_code})"
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise OCRRequestError("PaddleOCR-VL returned a non-JSON response") from exc
        text = _extract_message_text(result)
        if not text:
            raise OCRRequestError("PaddleOCR-VL returned no document text")
        return text


def _extract_message_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    ]
    return "\n".join(part for part in parts if part).strip()
