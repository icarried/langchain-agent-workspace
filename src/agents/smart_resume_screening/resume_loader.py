from __future__ import annotations

import re
from pathlib import Path

from src.agents.resume_review.resume_loader import load_resume_elements

from .schemas import CandidateProfile


def load_candidate(path: str | Path) -> CandidateProfile:
    resume_path = Path(path)
    elements = load_resume_elements(resume_path)
    text = "\n".join(element.text for element in elements)
    return CandidateProfile(
        filename=resume_path.name,
        display_name=_extract_name(text) or resume_path.stem,
        text=text,
    )


def _extract_name(text: str) -> str:
    for line in text.splitlines()[:10]:
        stripped = line.strip().strip("# ")
        match = re.search(r"(姓名|候选人)[:：]\s*([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z·\s]{1,20})", stripped)
        if match:
            return match.group(2).strip()
        if 2 <= len(stripped) <= 12 and not any(token in stripped for token in ["简历", "经历", "技能"]):
            return stripped
    return ""

