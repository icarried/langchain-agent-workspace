from __future__ import annotations

import re

from .schemas import DocumentChunk, DocumentElement

HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百千万0-9]+[章节部分]|附件[一二三四五六七八九十0-9]*|[一二三四五六七八九十]+、|\d+[.、])"
)


def chunk_elements(
    elements: list[DocumentElement],
    max_chars: int = 16000,
    overlap_chars: int = 800,
) -> list[DocumentChunk]:
    """Chunk tender content by headings first, then by length.

    A 16k Chinese-character chunk leaves room for reference rules, prompts, and
    model output even when using smaller 32k-token model variants.
    """
    if max_chars <= 2000:
        raise ValueError("max_chars must be greater than 2000")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    chunks: list[DocumentChunk] = []
    current: list[DocumentElement] = []
    current_title = "文档开头"

    for element in elements:
        current_size = sum(len(e.text) + 2 for e in current)
        too_large = current_size + len(element.text) + 2 > max_chars
        if too_large:
            chunks.extend(_flush(current, current_title, len(chunks), max_chars, overlap_chars))
            current = _overlap_tail(current, overlap_chars)
            if not current:
                current_title = element.text[:80]
        if _is_heading(element) and not current:
            current_title = element.text[:80]
        current.append(element)

    chunks.extend(_flush(current, current_title, len(chunks), max_chars, overlap_chars))
    return chunks


def _is_heading(element: DocumentElement) -> bool:
    if element.kind == "table":
        return False
    style = element.style.lower()
    if style.startswith("heading") or "标题" in element.style:
        return True
    text = element.text.strip()
    return len(text) <= 80 and bool(HEADING_RE.match(text))


def _flush(
    elements: list[DocumentElement],
    title: str,
    start_index: int,
    max_chars: int,
    overlap_chars: int,
) -> list[DocumentChunk]:
    if not elements:
        return []

    chunks: list[DocumentChunk] = []
    part: list[DocumentElement] = []
    part_size = 0
    for element in elements:
        size = len(element.text) + 2
        if part and part_size + size > max_chars:
            chunks.append(_make_chunk(part, title, start_index + len(chunks)))
            part = _overlap_tail(part, overlap_chars)
            part_size = sum(len(e.text) + 2 for e in part)
        part.append(element)
        part_size += size
    if part:
        chunks.append(_make_chunk(part, title, start_index + len(chunks)))
    return chunks


def _make_chunk(elements: list[DocumentElement], title: str, index: int) -> DocumentChunk:
    display_title = _first_heading(elements) or title
    text = "\n\n".join(f"[{e.kind}#{e.index}]\n{e.text}" for e in elements)
    return DocumentChunk(
        chunk_id=f"chunk-{index + 1:03d}",
        title=display_title,
        text=text,
        start_element=elements[0].index,
        end_element=elements[-1].index,
        char_count=len(text),
    )


def _first_heading(elements: list[DocumentElement]) -> str:
    for element in elements:
        if _is_heading(element):
            return element.text[:80]
    return ""


def _overlap_tail(elements: list[DocumentElement], overlap_chars: int) -> list[DocumentElement]:
    if overlap_chars == 0:
        return []
    tail: list[DocumentElement] = []
    total = 0
    for element in reversed(elements):
        tail.insert(0, element)
        total += len(element.text) + 2
        if total >= overlap_chars:
            break
    return tail
