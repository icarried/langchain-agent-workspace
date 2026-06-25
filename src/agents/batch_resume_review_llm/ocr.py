from __future__ import annotations

import base64
import os
from typing import Any


DEFAULT_OCR_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_OCR_MODEL = "qwen3.5-ocr"
DEFAULT_OCR_TIMEOUT_SECONDS = 120.0
OCR_PROMPT = (
    "请逐字提取这页简历中的全部可见文字，保留标题、段落、列表和表格的阅读顺序。"
    "不要总结、改写、补全或推测；无法辨认的字符使用 ?。只返回提取后的正文。"
)


def ocr_image_bytes(data: bytes, mime_type: str, *, source: str) -> str:
    """Extract resume text from one image with Alibaba Cloud Model Studio OCR."""
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            f"OCR is required for '{source}', but DASHSCOPE_API_KEY is not configured"
        )
    if not data:
        raise ValueError(f"OCR input is empty for '{source}'")

    try:
        timeout = float(
            os.getenv(
                "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS",
                str(DEFAULT_OCR_TIMEOUT_SECONDS),
            )
        )
    except ValueError as exc:
        raise ValueError(
            "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS must be a positive number"
        ) from exc
    if timeout <= 0:
        raise ValueError(
            "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS must be a positive number"
        )

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("BATCH_RESUME_REVIEW_OCR_BASE_URL", DEFAULT_OCR_BASE_URL),
        timeout=timeout,
    )
    encoded = base64.b64encode(data).decode("ascii")
    try:
        response = client.chat.completions.create(
            model=os.getenv("BATCH_RESUME_REVIEW_OCR_MODEL", DEFAULT_OCR_MODEL),
            messages=[
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
            extra_body={"ocr_options": {"task": "document_parsing"}},
        )
    except Exception as exc:
        raise ValueError(f"Bailian OCR failed for '{source}': {exc}") from exc

    text = _message_text(response)
    if not text.strip():
        raise ValueError(f"Bailian OCR returned no text for '{source}'")
    return text.strip()


def _message_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    content = getattr(getattr(choices[0], "message", None), "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("ocr_result")
            else:
                value = getattr(item, "text", None)
            if value:
                parts.append(str(value))
        return "\n".join(parts)
    return str(content or "")
