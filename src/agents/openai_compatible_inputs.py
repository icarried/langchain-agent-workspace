from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AttachmentReference:
    url: str
    filename: str | None = None
    media_type: str | None = None
    source_kind: str = "unknown"


def message_content_to_text_and_urls(content: Any) -> tuple[str, list[str]]:
    text, attachments = message_content_to_text_and_attachments(content)
    return text, [item.url for item in attachments]


def message_content_to_text_and_attachments(
    content: Any,
) -> tuple[str, list[AttachmentReference]]:
    if isinstance(content, str):
        return content, []
    if isinstance(content, dict):
        return _message_part_to_text_and_attachments(content)
    if isinstance(content, list):
        text_parts: list[str] = []
        attachments: list[AttachmentReference] = []
        for item in content:
            if isinstance(item, dict):
                text, item_attachments = _message_part_to_text_and_attachments(item)
                if text:
                    text_parts.append(text)
                attachments.extend(item_attachments)
        return "\n".join(text_parts), dedupe_attachment_references(attachments)
    return "", []


def messages_to_text_and_urls(messages: list[Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    urls: list[str] = []
    for message in messages:
        text, message_urls = message_content_to_text_and_urls(message.content)
        if text:
            text_parts.append(text)
        urls.extend(message_urls)
    return "\n\n".join(text_parts), dedupe(urls)


def extract_labeled_paths(
    text: str,
    start_labels: list[str],
    end_labels: list[str],
    *,
    extra_paths: list[str] | None = None,
) -> list[str]:
    block = extract_section_block(text, start_labels, end_labels)
    paths = extract_paths_from_block(block)
    if extra_paths:
        paths.extend(extra_paths)
    return dedupe(paths)


def extract_text_before_labeled_section(text: str, labels: list[str]) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("-* ")
        if any(starts_section(line, label) for label in labels):
            break
        lines.append(raw_line.rstrip())
    return "\n".join(lines).strip()


def extract_section_block(
    text: str,
    start_labels: list[str],
    end_labels: list[str],
) -> str:
    lines: list[str] = []
    collecting = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line and not collecting:
            continue
        if any(starts_section(line.strip("-* "), label) for label in start_labels):
            collecting = True
            line = strip_section_label(line.strip("-* "))
            if line:
                lines.append(line)
            continue
        if collecting and any(starts_section(line.strip("-* "), label) for label in end_labels):
            collecting = False
            continue
        if collecting:
            lines.append(line)
    return "\n".join(lines).strip()


def extract_paths_from_block(block: str) -> list[str]:
    json_paths = extract_json_array_paths(block)
    if json_paths:
        return dedupe(json_paths)

    paths: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip().strip("-* ")
        if line:
            paths.extend(extract_paths_from_line(line))
    return dedupe(paths)


def extract_json_array_paths(block: str) -> list[str]:
    text = block.strip()
    if not text:
        return []
    start = text.find("[")
    if start < 0:
        return []
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def extract_paths_from_line(line: str) -> list[str]:
    urls = [_clean_url(url) for url in re.findall(r"https?://[^\s\"'<>，]+", line)]
    if urls:
        return [url for url in urls if url]

    labeled_path = _extract_path_after_filename_label(line)
    if labeled_path:
        return extract_paths_from_line(labeled_path)

    parts = [part.strip().strip("\"'") for part in re.split(r"[,，;；]", line)]
    return [part for part in parts if part and not part.endswith((":", "："))]


def starts_section(line: str, label: str) -> bool:
    return bool(re.match(rf"^{re.escape(label)}\s*[:：]", line, flags=re.IGNORECASE))


def strip_section_label(line: str) -> str:
    return re.sub(r"^[^:：]+[:：]\s*", "", line, count=1).strip()


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def attachment_reference_from_value(
    value: Any,
    *,
    source_kind: str,
) -> AttachmentReference | None:
    if isinstance(value, str):
        url = value.strip()
        if _is_http_url(url):
            return AttachmentReference(url=url, source_kind=source_kind)
        return None
    if not isinstance(value, dict):
        return None

    url = _extract_url_value(value.get("url"))
    if not url:
        url = _extract_url_value(value.get("file_url"))
    if not url:
        return None
    filename = value.get("filename")
    media_type = value.get("mime_type") or value.get("media_type")
    return AttachmentReference(
        url=url,
        filename=filename.strip() if isinstance(filename, str) and filename.strip() else None,
        media_type=(
            media_type.strip()
            if isinstance(media_type, str) and media_type.strip()
            else None
        ),
        source_kind=source_kind,
    )


def dedupe_attachment_references(
    values: list[AttachmentReference],
) -> list[AttachmentReference]:
    positions: dict[str, int] = {}
    result: list[AttachmentReference] = []
    for value in values:
        key = value.url.lower()
        position = positions.get(key)
        if position is None:
            positions[key] = len(result)
            result.append(value)
            continue
        existing = result[position]
        if (
            (not existing.filename and value.filename)
            or (not existing.media_type and value.media_type)
        ):
            result[position] = AttachmentReference(
                url=existing.url,
                filename=value.filename or existing.filename,
                media_type=value.media_type or existing.media_type,
                source_kind=value.source_kind,
            )
    return result


def _message_part_to_text_and_attachments(
    part: dict[str, Any],
) -> tuple[str, list[AttachmentReference]]:
    text_parts: list[str] = []
    attachments: list[AttachmentReference] = []
    if isinstance(part.get("text"), str):
        text_parts.append(part["text"])
    if isinstance(part.get("input_text"), str):
        text_parts.append(part["input_text"])

    for key in ("file_url", "image_url"):
        value = part.get(key)
        url = _extract_url_value(value)
        if url:
            metadata = value if isinstance(value, dict) else {}
            filename = metadata.get("filename") or part.get("filename")
            media_type = (
                metadata.get("mime_type")
                or metadata.get("media_type")
                or part.get("mime_type")
                or part.get("media_type")
            )
            attachments.append(
                AttachmentReference(
                    url=url,
                    filename=(
                        filename.strip()
                        if isinstance(filename, str) and filename.strip()
                        else None
                    ),
                    media_type=(
                        media_type.strip()
                        if isinstance(media_type, str) and media_type.strip()
                        else None
                    ),
                    source_kind=key,
                )
            )

    url = _extract_url_value(part.get("url"))
    if url:
        reference = attachment_reference_from_value(part, source_kind="url")
        if reference:
            attachments.append(reference)
    return "\n".join(text_parts), dedupe_attachment_references(attachments)


def _extract_url_value(value: Any) -> str:
    if isinstance(value, str) and _is_http_url(value):
        return value.strip()
    if isinstance(value, dict):
        url = value.get("url")
        if isinstance(url, str) and _is_http_url(url):
            return url.strip()
    return ""


def _extract_path_after_filename_label(line: str) -> str:
    match = re.match(r"^.+?\.[A-Za-z0-9]{1,8}\s*[:：]\s*(.+)$", line)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def _clean_url(url: str) -> str:
    return url.rstrip("，,。；;）)]}")


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))
