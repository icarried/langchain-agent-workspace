from __future__ import annotations

import json
import re
from typing import Any

import httpx
from src.model_gateway import gpu_stack_connection

from .inputs import bytes_to_data_url, decode_data_url, is_http_url
from .prompts import EDIT_REWRITE_PROMPT, GENERATION_REWRITE_PROMPT, rewrite_user_text
from .settings import ImageGenerationSettings


class GPUStackRequestError(RuntimeError):
    """A sanitized GPU Stack request failure."""


class GPUStackClient:
    def __init__(
        self,
        settings: ImageGenerationSettings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or ImageGenerationSettings()
        connection = gpu_stack_connection()
        self.base_url = connection.base_url
        self.api_key = connection.api_key
        self.transport = transport

    def rewrite_prompt(
        self,
        *,
        instruction: str,
        history: str,
        image_data_url: str | None,
    ) -> str:
        system_prompt = EDIT_REWRITE_PROMPT if image_data_url else GENERATION_REWRITE_PROMPT
        user_text = rewrite_user_text(instruction, history)
        content: str | list[dict[str, Any]]
        if image_data_url:
            content = [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            content = user_text

        payload = self._post_chat(
            {
                "model": self.settings.image_prompt_rewrite_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                "stream": False,
                "temperature": 0.2,
                "max_tokens": 1200,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False},
            }
        )
        text = extract_text_content(payload)
        return parse_rewritten_prompt(text)

    def generate(
        self,
        *,
        rewritten_prompt: str,
        image_data_url: str | None,
    ) -> str:
        model = (
            self.settings.image_edit_model
            if image_data_url
            else self.settings.image_generation_model
        )
        content: str | list[dict[str, Any]]
        if image_data_url:
            content = [
                {"type": "text", "text": rewritten_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            content = rewritten_prompt
        payload = self._post_chat(
            {
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
        )
        return extract_image_reference(
            payload,
            max_bytes=self.settings.image_agent_max_input_bytes * 2,
        )

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                timeout=self.settings.image_agent_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise GPUStackRequestError("GPU Stack请求超时") from exc
        except httpx.HTTPError as exc:
            raise GPUStackRequestError("GPU Stack连接失败") from exc
        if response.status_code >= 400:
            raise GPUStackRequestError(
                f"GPU Stack请求失败（HTTP {response.status_code}）"
            )
        try:
            value = response.json()
        except ValueError as exc:
            raise GPUStackRequestError("GPU Stack返回了非JSON响应") from exc
        if not isinstance(value, dict):
            raise GPUStackRequestError("GPU Stack响应格式无效")
        return value


def extract_text_content(payload: dict[str, Any]) -> str:
    message = _first_message(payload)
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "".join(texts).strip()
    raise GPUStackRequestError("提示词改写模型没有返回文本")


def parse_rewritten_prompt(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GPUStackRequestError("提示词改写结果不是有效JSON") from exc
    if not isinstance(payload, dict):
        raise GPUStackRequestError("提示词改写结果不是JSON对象")
    prompt = payload.get("rewritten_prompt") or payload.get("Rewritten")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GPUStackRequestError("提示词改写结果缺少 rewritten_prompt")
    return " ".join(prompt.split())


def extract_image_reference(payload: dict[str, Any], *, max_bytes: int) -> str:
    message = _first_message(payload)
    candidates = _image_candidates(message)
    if not candidates:
        candidates = _image_candidates(payload.get("data"))
    for candidate, mime_type in candidates:
        if candidate.startswith("data:image/"):
            decode_data_url(candidate, max_bytes=max_bytes)
            return candidate
        if is_http_url(candidate):
            return candidate
        try:
            raw = _decode_output_base64(candidate, max_bytes=max_bytes)
        except ValueError:
            continue
        return bytes_to_data_url(raw, mime_type or "image/png")
    raise GPUStackRequestError("图片模型没有返回可识别的图片")


def _first_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GPUStackRequestError("GPU Stack响应缺少choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise GPUStackRequestError("GPU Stack响应缺少message")
    return message


def _image_candidates(value: Any) -> list[tuple[str, str | None]]:
    candidates: list[tuple[str, str | None]] = []
    if isinstance(value, list):
        for item in value:
            candidates.extend(_image_candidates(item))
        return candidates
    if isinstance(value, dict):
        image_url = value.get("image_url")
        if isinstance(image_url, str):
            candidates.append((image_url.strip(), None))
        elif isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
            candidates.append((image_url["url"].strip(), image_url.get("mime_type")))
        for key in ("b64_json", "base64", "image"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                candidates.append(
                    (
                        candidate.strip(),
                        value.get("mime_type") or value.get("media_type") or "image/png",
                    )
                )
        for key in ("content", "images", "data"):
            if key in value:
                candidates.extend(_image_candidates(value[key]))
        return candidates
    if not isinstance(value, str):
        return candidates
    stripped = value.strip()
    if stripped.startswith(("data:image/", "http://", "https://")):
        candidates.append((stripped, None))
    for match in re.finditer(
        r"!\[[^\]]*\]\((data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=_-]+|https?://[^)\s]+)\)",
        stripped,
    ):
        candidates.append((match.group(1), None))
    return candidates


def _decode_output_base64(value: str, *, max_bytes: int) -> bytes:
    import base64
    import binascii

    compact = re.sub(r"\s+", "", value)
    if not compact or len(compact) * 3 // 4 > max_bytes:
        raise ValueError
    try:
        return base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError from exc
