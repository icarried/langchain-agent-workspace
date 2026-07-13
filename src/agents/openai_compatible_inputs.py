from __future__ import annotations

import json
import re
from typing import Any


def message_content_to_text_and_urls(content: Any) -> tuple[str, list[str]]:
    if isinstance(content, str):
        return content, []
    if isinstance(content, dict):
        return _message_part_to_text_and_urls(content)
    if isinstance(content, list):
        text_parts: list[str] = []
        urls: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text, item_urls = _message_part_to_text_and_urls(item)
                if text:
                    text_parts.append(text)
                urls.extend(item_urls)
        return "\n".join(text_parts), dedupe(urls)
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


def _message_part_to_text_and_urls(part: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    urls: list[str] = []
    if isinstance(part.get("text"), str):
        text_parts.append(part["text"])
    if isinstance(part.get("input_text"), str):
        text_parts.append(part["input_text"])

    for key in ("file_url", "image_url"):
        value = part.get(key)
        url = _extract_url_value(value)
        if url:
            urls.append(url)

    url = _extract_url_value(part.get("url"))
    if url:
        urls.append(url)
    return "\n".join(text_parts), dedupe(urls)


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
