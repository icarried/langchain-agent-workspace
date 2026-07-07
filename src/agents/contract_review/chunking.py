from __future__ import annotations

import re

from .schemas import ContractChunk, ContractElement


SECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^第[一二三四五六七八九十百\d]+[章节条]",
        r"^[一二三四五六七八九十]+[、.．]",
        r"^\d+(\.\d+)*[、.．]?",
        r"^(合同主体|标的|价款|付款|交付|验收|保密|知识产权|违约责任|争议解决|合同解除|生效|终止)",
    ]
]


def chunk_elements(elements: list[ContractElement], max_chars: int = 12000) -> list[ContractChunk]:
    chunks: list[ContractChunk] = []
    current: list[ContractElement] = []

    for element in elements:
        next_text = _format_element(element)
        current_chars = sum(len(_format_element(item)) for item in current)
        if current and (_is_section_heading(element) or current_chars + len(next_text) > max_chars):
            chunks.append(_make_chunk(current, len(chunks) + 1))
            current = []
        current.append(element)

    if current:
        chunks.append(_make_chunk(current, len(chunks) + 1))
    return chunks


def _make_chunk(elements: list[ContractElement], sequence: int) -> ContractChunk:
    text = "\n".join(_format_element(element) for element in elements)
    first = elements[0]
    title = _title_from(first)
    return ContractChunk(
        chunk_id=f"chunk-{sequence:03d}",
        title=title,
        text=text,
        start_element=elements[0].index,
        end_element=elements[-1].index,
        char_count=len(text),
    )


def _format_element(element: ContractElement) -> str:
    return f"[{element.kind}#{element.index}] {element.text}"


def _title_from(element: ContractElement) -> str:
    text = element.text.strip().replace("|", "/")
    if len(text) <= 36:
        return text
    return f"{text[:36]}..."


def _is_section_heading(element: ContractElement) -> bool:
    text = element.text.strip()
    if element.style.lower().startswith("heading"):
        return True
    return any(pattern.match(text) for pattern in SECTION_PATTERNS)

