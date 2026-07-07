from __future__ import annotations

import re

from .schemas import ScreeningCriteria


DEFAULT_WEIGHTS = {
    "education_weight": 20,
    "experience_weight": 35,
    "skill_weight": 25,
    "project_weight": 15,
    "soft_weight": 5,
}


def build_criteria(
    *,
    job_description: str = "",
    position_name: str = "",
    department: str = "",
    level_range: str = "",
    hard_conditions: list[str] | None = None,
    bonus_conditions: list[str] | None = None,
    reject_conditions: list[str] | None = None,
) -> ScreeningCriteria:
    extracted_hard = _extract_list(job_description, ["硬性条件", "必须满足", "任职要求"])
    extracted_bonus = _extract_list(job_description, ["优先条件", "加分项", "优先"])
    extracted_reject = _extract_list(job_description, ["淘汰条件", "一票否决", "不接受"])
    return ScreeningCriteria(
        position_name=position_name or _extract_scalar(job_description, "职位名称") or "未说明",
        department=department or _extract_scalar(job_description, "所属部门") or "未说明",
        level_range=level_range or _extract_scalar(job_description, "职级范围") or "未说明",
        hard_conditions=tuple(_clean_conditions((hard_conditions or []) + extracted_hard)),
        bonus_conditions=tuple(_clean_conditions((bonus_conditions or []) + extracted_bonus)),
        reject_conditions=tuple(_clean_conditions((reject_conditions or []) + extracted_reject)),
        **DEFAULT_WEIGHTS,
    )


def _extract_scalar(text: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}\s*[：:]\s*(.+)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_list(text: str, labels: list[str]) -> list[str]:
    results: list[str] = []
    lines = text.splitlines()
    capture = False
    for line in lines:
        stripped = line.strip().strip("-* ")
        if not stripped:
            capture = False
            continue
        if any(label in stripped for label in labels):
            after = re.split(r"[：:]", stripped, maxsplit=1)
            if len(after) == 2:
                results.extend(_split_conditions(after[1]))
            capture = True
            continue
        if capture and re.match(r"^[\d一二三四五六七八九十]+[、.．)]", stripped):
            results.extend(_split_conditions(re.sub(r"^[\d一二三四五六七八九十]+[、.．)]\s*", "", stripped)))
        elif capture and re.match(r"^-", line.strip()):
            results.extend(_split_conditions(stripped))
    return results


def _clean_conditions(items: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        text = item.strip().strip("，,。；; ")
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _split_conditions(text: str) -> list[str]:
    parts = re.split(r"[，,；;/、]", text)
    return [part.strip() for part in parts if part.strip()]

