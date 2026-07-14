from __future__ import annotations

import re
from src.reference_data.universities import (
    DEFAULT_UNIVERSITY_REFERENCE_DIR,
    load_university_references,
)


def test_fixed_and_time_versioned_university_lists_have_expected_counts() -> None:
    assert _numbered_count("985工程高校名单_教育部.md") == 39
    assert _numbered_count("211工程高校名单_教育部.md") == 112
    assert _numbered_count("双一流建设高校名单_第二轮_2022.md") == 147


def test_university_references_preserve_sources_aliases_and_dynamic_rules() -> None:
    references = load_university_references()

    assert "教育部" in references
    assert "国防科学技术大学（现常用名：国防科技大学）" in references
    assert "第二军医大学（现名：海军军医大学）" in references
    assert "本地核对日期：2026-06-22" in references
    assert "不存在全国统一、永久不变的“一本高校名单”" in references
    assert "不得凭模型记忆给出名次" in references
    assert "https://www.topuniversities.com/world-university-rankings" in references


def test_loader_accepts_single_reference_file() -> None:
    path = DEFAULT_UNIVERSITY_REFERENCE_DIR / "985工程高校名单_教育部.md"

    references = load_university_references(path)

    assert "高校名单（39 所）" in references
    assert "211 工程高校名单" not in references


def _numbered_count(filename: str) -> int:
    path = DEFAULT_UNIVERSITY_REFERENCE_DIR / filename
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\d+\. ", text, flags=re.MULTILINE))
