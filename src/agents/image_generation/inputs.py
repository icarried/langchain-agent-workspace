from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any

from src.agents.remote_files import is_http_url, read_remote_file


SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
DATA_URL_RE = re.compile(
    r"^data:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=_-]+)$",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ParsedConversation:
    instruction: str
    history: str
    image_source: str | None
    image_from_current_user: bool


def parse_conversation(messages: list[Any], *, history_limit: int = 8) -> ParsedConversation:
    normalized: list[tuple[str, str, list[str]]] = []
    for message in messages:
        role = _field(message, "role")
        text, images = content_to_text_and_images(_field(message, "content"))
        normalized.append((str(role or ""), text.strip(), images))

    latest_user = next(
        (
            index
            for index in range(len(normalized) - 1, -1, -1)
            if normalized[index][0] == "user"
            and (normalized[index][1] or normalized[index][2])
        ),
        None,
    )
    if latest_user is None:
        raise ValueError("请提供生图或图片编辑指令")

    _, instruction, current_images = normalized[latest_user]
    if not instruction:
        instruction = "请根据对话上下文编辑这张图片。"
    if len(current_images) > 1:
        raise ValueError("首版每次只支持一张用户输入图片")

    image_source = current_images[0] if current_images else None
    from_current = bool(image_source)
    if not image_source:
        for role, _, images in reversed(normalized[:latest_user]):
            if role == "assistant" and images:
                image_source = images[-1]
                break

    history_items = [
        f"{role}: {text}"
        for role, text, _ in normalized[max(0, latest_user - history_limit) : latest_user]
        if text and role in {"user", "assistant", "system"}
    ]
    return ParsedConversation(
        instruction=instruction,
        history="\n".join(history_items),
        image_source=image_source,
        image_from_current_user=from_current,
    )


def content_to_text_and_images(content: Any) -> tuple[str, list[str]]:
    if isinstance(content, str):
        return content, []
    if isinstance(content, dict):
        return _part_to_text_and_images(content)
    if not isinstance(content, list):
        return "", []

    texts: list[str] = []
    images: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        text, part_images = _part_to_text_and_images(part)
        if text:
            texts.append(text)
        images.extend(part_images)
    return "\n".join(texts), _dedupe(images)


def normalize_image_source(source: str, *, max_bytes: int) -> str:
    if is_http_url(source):
        data, declared_mime = read_remote_file(source, max_bytes=max_bytes)
        mime = detect_image_mime(data)
        if declared_mime.startswith("image/") and declared_mime != mime:
            raise ValueError("远程图片MIME与实际格式不一致")
        return bytes_to_data_url(data, mime)
    if source.startswith("data:"):
        mime, data = decode_data_url(source, max_bytes=max_bytes)
        detected = detect_image_mime(data)
        if detected != mime:
            raise ValueError("Base64图片MIME与实际格式不一致")
        return bytes_to_data_url(data, detected)
    raise ValueError("图片必须是HTTP(S) URL或Base64 data URL")


def raw_base64_to_data_url(data: str, mime_type: str, *, max_bytes: int) -> str:
    normalized_mime = mime_type.lower().strip()
    if normalized_mime not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ValueError("不支持的图片MIME类型")
    decoded = _decode_base64(data, max_bytes=max_bytes)
    detected = detect_image_mime(decoded)
    if detected != normalized_mime:
        raise ValueError("Base64图片MIME与实际格式不一致")
    return bytes_to_data_url(decoded, detected)


def decode_data_url(value: str, *, max_bytes: int) -> tuple[str, bytes]:
    match = DATA_URL_RE.fullmatch(value.strip())
    if not match:
        raise ValueError("无效的Base64图片data URL")
    mime = match.group(1).lower()
    if mime not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ValueError("不支持的图片MIME类型")
    return mime, _decode_base64(match.group(2), max_bytes=max_bytes)


def bytes_to_data_url(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"


def detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("输入内容不是支持的图片格式")


def is_readiness_probe(messages: list[Any]) -> bool:
    if len(messages) != 1:
        return False
    role = _field(messages[0], "role")
    text, images = content_to_text_and_images(_field(messages[0], "content"))
    normalized = re.sub(r"[\s,.!?，。！？]+", "", text).lower()
    return role == "user" and not images and normalized in {
        "hi",
        "hello",
        "你好",
        "ping",
        "test",
        "测试",
        "你是谁",
    }


def _part_to_text_and_images(part: dict[str, Any]) -> tuple[str, list[str]]:
    texts = [
        value
        for key in ("text", "input_text")
        if isinstance((value := part.get(key)), str)
    ]
    images: list[str] = []
    image_url = part.get("image_url")
    if isinstance(image_url, str):
        images.append(image_url.strip())
    elif isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
        images.append(image_url["url"].strip())

    raw = part.get("image_base64")
    if raw is not None:
        if isinstance(raw, dict):
            data = raw.get("data") or raw.get("b64_json")
            mime = raw.get("mime_type") or raw.get("media_type")
        else:
            data = raw
            mime = part.get("mime_type")
        if not isinstance(data, str) or not isinstance(mime, str):
            raise ValueError("原始Base64图片必须同时提供data和mime_type")
        images.append(f"raw-base64:{mime}:{data}")
    return "\n".join(texts), [value for value in images if value]


def normalize_extracted_source(source: str, *, max_bytes: int) -> str:
    if source.startswith("raw-base64:"):
        _, mime, data = source.split(":", 2)
        return raw_base64_to_data_url(data, mime, max_bytes=max_bytes)
    return normalize_image_source(source, max_bytes=max_bytes)


def _decode_base64(value: str, *, max_bytes: int) -> bytes:
    compact = re.sub(r"\s+", "", value)
    estimated = len(compact) * 3 // 4
    if estimated > max_bytes:
        raise ValueError("图片超过 IMAGE_AGENT_MAX_INPUT_BYTES")
    try:
        data = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("无效的Base64图片") from exc
    if len(data) > max_bytes:
        raise ValueError("图片超过 IMAGE_AGENT_MAX_INPUT_BYTES")
    return data


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
