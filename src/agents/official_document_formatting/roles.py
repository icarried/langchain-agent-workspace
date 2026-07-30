"""Deterministic paragraph-role classification for official documents."""

from __future__ import annotations

import re
from enum import StrEnum


class ParagraphRole(StrEnum):
    """Semantic roles whose presentation is defined by the formatting standard."""

    EMPTY = "empty"
    TITLE = "title"
    DOCUMENT_NUMBER = "document_number"
    SIGNER_LINE = "signer_line"
    MAIN_RECIPIENT = "main_recipient"
    BODY = "body"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    ATTACHMENT_NOTE = "attachment_note"
    ATTACHMENT_ITEM = "attachment_item"
    SIGNATURE = "signature"
    DATE = "date"
    ANNOTATION = "annotation"
    OFFICIAL_ATTACHMENT_MARKER = "official_attachment_marker"
    OFFICIAL_ATTACHMENT_TITLE = "official_attachment_title"
    IMPRINT = "imprint"


TITLE_PATTERN = re.compile(
    r"^关于.+(?:请示|报告|通知|通报|决定|意见|函|纪要|公告|批复|方案)$"
)
LEVEL_1_PATTERN = re.compile(r"^[一二三四五六七八九十百]+、")
LEVEL_2_PATTERN = re.compile(r"^(?:（[一二三四五六七八九十百]+）|方式[一二三四五六])")
LEVEL_3_PATTERN = re.compile(r"^\d+[\.．、]")
LEVEL_4_PATTERN = re.compile(r"^（\d+）")
DATE_PATTERN = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$")
DOCUMENT_NUMBER_PATTERN = re.compile(r"^.{0,20}〔\d{4}〕\d+号$")
SIGNER_LINE_PATTERN = re.compile(r"^签发人\s*[：:].+")
ANNOTATION_PATTERN = re.compile(r"^（.+）$")
OFFICIAL_ATTACHMENT_MARKER_PATTERN = re.compile(r"^附件(?:\s*\d+)?$")
SIGNATURE_PATTERN = re.compile(
    r"(?:公司|集团|委员会|办公室|人民政府|政府|部门|中心|研究院|分公司|事业部|部|局|厅|院|所|处|科)$"
)


def classify_paragraphs(texts: list[str]) -> list[ParagraphRole]:
    """Classify paragraphs without changing or normalizing their visible text."""
    stripped = [text.strip() for text in texts]
    non_empty = [index for index, text in enumerate(stripped) if text]
    result = [ParagraphRole.EMPTY for _ in texts]
    if not non_empty:
        return result

    title_index = _find_title_index(stripped, non_empty)
    first_heading_index = next(
        (index for index in non_empty if LEVEL_1_PATTERN.match(stripped[index])),
        None,
    )
    date_indices = {
        index for index in non_empty if DATE_PATTERN.fullmatch(stripped[index])
    }
    signature_indices = {
        previous
        for date_index in date_indices
        if (previous := _previous_non_empty(non_empty, date_index)) is not None
        and _looks_like_signature(stripped[previous])
    }
    attachment_roles = _find_attachment_roles(
        stripped,
        non_empty,
        date_indices | signature_indices,
    )
    last_date_index = max(date_indices, default=-1)
    formal_attachment_titles = _formal_attachment_title_indices(stripped, non_empty)

    for index in non_empty:
        text = stripped[index]
        if index == title_index:
            role = ParagraphRole.TITLE
        elif DOCUMENT_NUMBER_PATTERN.fullmatch(text):
            role = ParagraphRole.DOCUMENT_NUMBER
        elif SIGNER_LINE_PATTERN.match(text):
            role = ParagraphRole.SIGNER_LINE
        elif index in date_indices:
            role = ParagraphRole.DATE
        elif index in signature_indices:
            role = ParagraphRole.SIGNATURE
        elif index > last_date_index >= 0 and ANNOTATION_PATTERN.fullmatch(text):
            role = ParagraphRole.ANNOTATION
        elif _is_imprint(text):
            role = ParagraphRole.IMPRINT
        elif index in attachment_roles:
            role = attachment_roles[index]
        elif OFFICIAL_ATTACHMENT_MARKER_PATTERN.fullmatch(text):
            role = ParagraphRole.OFFICIAL_ATTACHMENT_MARKER
        elif index in formal_attachment_titles:
            role = ParagraphRole.OFFICIAL_ATTACHMENT_TITLE
        elif LEVEL_1_PATTERN.match(text):
            role = ParagraphRole.HEADING_1
        elif LEVEL_2_PATTERN.match(text):
            role = ParagraphRole.HEADING_2
        elif LEVEL_3_PATTERN.match(text):
            role = ParagraphRole.HEADING_3
        elif LEVEL_4_PATTERN.match(text):
            role = ParagraphRole.HEADING_4
        elif _is_main_recipient(text, index, title_index, first_heading_index):
            role = ParagraphRole.MAIN_RECIPIENT
        else:
            role = ParagraphRole.BODY
        result[index] = role
    return result


def _find_title_index(texts: list[str], non_empty: list[int]) -> int:
    for index in non_empty[:8]:
        if TITLE_PATTERN.match(texts[index]):
            return index
    for index in non_empty:
        text = texts[index]
        if DOCUMENT_NUMBER_PATTERN.fullmatch(text) or SIGNER_LINE_PATTERN.match(text):
            continue
        return index
    return non_empty[0]


def _previous_non_empty(non_empty: list[int], index: int) -> int | None:
    return next((candidate for candidate in reversed(non_empty) if candidate < index), None)


def _find_attachment_roles(
    texts: list[str],
    non_empty: list[int],
    closing_indices: set[int],
) -> dict[int, ParagraphRole]:
    start = next(
        (
            index
            for index in non_empty
            if texts[index].startswith(("附件：", "附件:"))
        ),
        None,
    )
    if start is None:
        return {}
    closing = min((index for index in closing_indices if index > start), default=None)
    roles: dict[int, ParagraphRole] = {start: ParagraphRole.ATTACHMENT_NOTE}
    for index in non_empty:
        if index > start and (closing is None or index < closing):
            roles[index] = ParagraphRole.ATTACHMENT_ITEM
    return roles


def _looks_like_signature(text: str) -> bool:
    return (
        1 <= len(text) <= 30
        and not text.startswith("附件")
        and not LEVEL_1_PATTERN.match(text)
        and not LEVEL_2_PATTERN.match(text)
        and not LEVEL_3_PATTERN.match(text)
        and not LEVEL_4_PATTERN.match(text)
        and bool(SIGNATURE_PATTERN.search(text))
    )


def _is_main_recipient(
    text: str,
    index: int,
    title_index: int,
    first_heading_index: int | None,
) -> bool:
    if not text.endswith(("：", ":")) or len(text) > 40:
        return False
    if text.startswith(("附件：", "附件:", "抄送：", "抄送:")):
        return False
    return index > title_index and (
        first_heading_index is None or index < first_heading_index
    )


def _is_imprint(text: str) -> bool:
    return text.startswith(("抄送：", "抄送:", "印发：", "印发:")) or "印发" in text


def _formal_attachment_title_indices(
    texts: list[str],
    non_empty: list[int],
) -> set[int]:
    result: set[int] = set()
    for marker_index in non_empty:
        if not OFFICIAL_ATTACHMENT_MARKER_PATTERN.fullmatch(texts[marker_index]):
            continue
        following = next(
            (index for index in non_empty if index > marker_index),
            None,
        )
        if following is not None:
            result.add(following)
    return result
