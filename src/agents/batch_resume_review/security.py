from __future__ import annotations

import re
from typing import Iterable

from .schemas import ResumeElement

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"忽略.{0,16}(?:内容|指令|规则|条件|审查)", re.IGNORECASE),
    re.compile(r"无视.{0,16}(?:内容|指令|规则|条件|审查)", re.IGNORECASE),
    re.compile(r"(?:强制|直接).{0,16}(?:通过|录用|第一名|最高分|满分)", re.IGNORECASE),
    re.compile(r"(?:给|打).{0,8}(?:100|最高|满)分", re.IGNORECASE),
    re.compile(r"不要.{0,16}(?:检查|审查|披露|报告)", re.IGNORECASE),
    re.compile(r"ignore\s+(?:all\s+|previous\s+|prior\s+)?instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+|previous\s+|prior\s+)?instructions?", re.IGNORECASE),
)


def find_prompt_injections(elements: Iterable[ResumeElement]) -> list[str]:
    findings = []
    for element in elements:
        if any(pattern.search(element.text) for pattern in PROMPT_INJECTION_PATTERNS):
            findings.append(f"[{element.kind}#{element.index}] {element.text}")
    return findings
