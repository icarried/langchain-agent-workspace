from __future__ import annotations

import re

from .schemas import ResumeChunk, ResumeElement


SECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^(个人信息|基本信息|求职意向|教育经历|教育背景|工作经历|实习经历)$",
        r"^(项目经历|项目经验|技能|专业技能|证书|资格证书|作品|获奖|自我评价)$",
        r"^(profile|summary|education|experience|work experience|projects|skills|certifications)$",
    ]
]


def chunk_elements(elements: list[ResumeElement], max_chars: int = 12000) -> list[ResumeChunk]:
    chunks: list[ResumeChunk] = []
    current: list[ResumeElement] = []

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


def _make_chunk(elements: list[ResumeElement], sequence: int) -> ResumeChunk:
    text = "\n".join(_format_element(element) for element in elements)
    first = elements[0]
    title = _title_from(first)
    return ResumeChunk(
        chunk_id=f"chunk-{sequence:03d}",
        title=title,
        text=text,
        start_element=elements[0].index,
        end_element=elements[-1].index,
        char_count=len(text),
    )


def _format_element(element: ResumeElement) -> str:
    return f"[{element.kind}#{element.index}] {element.text}"


def _title_from(element: ResumeElement) -> str:
    text = element.text.strip().replace("|", "/")
    if len(text) <= 32:
        return text
    return f"{text[:32]}..."


def _is_section_heading(element: ResumeElement) -> bool:
    text = element.text.strip()
    if element.style.lower().startswith("heading"):
        return True
    return any(pattern.match(text) for pattern in SECTION_PATTERNS)
