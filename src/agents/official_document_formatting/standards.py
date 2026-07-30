"""Single source of truth for deterministic official-document formatting."""

from __future__ import annotations

from dataclasses import dataclass

from docx.enum.text import WD_ALIGN_PARAGRAPH

from .roles import ParagraphRole

FZXBS = "方正小标宋简体"
HEI = "黑体"
KAI = "楷体_GB2312"
FS = "仿宋_GB2312"
SONG = "宋体"
LATIN_FONT = "Times New Roman"

PAGE_WIDTH_CM = 21.0
PAGE_HEIGHT_CM = 29.7
TOP_MARGIN_CM = 3.7
BOTTOM_MARGIN_CM = 3.5
LEFT_MARGIN_CM = 2.8
RIGHT_MARGIN_CM = 2.6
FOOTER_DISTANCE_CM = 2.5

TITLE_SIZE_PT = 22
BODY_SIZE_PT = 16
IMPRINT_SIZE_PT = 14
PAGE_NUMBER_SIZE_PT = 14
TABLE_SIZE_PT = 12
EXACT_LINE_SPACING_TWIPS = 560
FIRST_LINE_INDENT_TWIPS = 640
FIRST_LINE_INDENT_CHARS = 200
ONE_CHAR_INDENT_TWIPS = 280
ONE_CHAR_INDENT_CHARS = 100


@dataclass(frozen=True)
class ParagraphStyleSpec:
    font: str
    size_pt: int
    alignment: WD_ALIGN_PARAGRAPH
    first_line_twips: int = 0
    first_line_chars: int = 0


ROLE_STYLES: dict[ParagraphRole, ParagraphStyleSpec] = {
    ParagraphRole.TITLE: ParagraphStyleSpec(
        FZXBS, TITLE_SIZE_PT, WD_ALIGN_PARAGRAPH.CENTER
    ),
    ParagraphRole.DOCUMENT_NUMBER: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.CENTER
    ),
    ParagraphRole.SIGNER_LINE: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.LEFT
    ),
    ParagraphRole.MAIN_RECIPIENT: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.LEFT
    ),
    ParagraphRole.BODY: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.JUSTIFY,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.HEADING_1: ParagraphStyleSpec(
        HEI,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.HEADING_2: ParagraphStyleSpec(
        KAI,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.HEADING_3: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.HEADING_4: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.ATTACHMENT_NOTE: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.ATTACHMENT_ITEM: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.SIGNATURE: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.RIGHT
    ),
    ParagraphRole.DATE: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.RIGHT
    ),
    ParagraphRole.ANNOTATION: ParagraphStyleSpec(
        FS,
        BODY_SIZE_PT,
        WD_ALIGN_PARAGRAPH.LEFT,
        FIRST_LINE_INDENT_TWIPS,
        FIRST_LINE_INDENT_CHARS,
    ),
    ParagraphRole.OFFICIAL_ATTACHMENT_MARKER: ParagraphStyleSpec(
        FS, BODY_SIZE_PT, WD_ALIGN_PARAGRAPH.LEFT
    ),
    ParagraphRole.OFFICIAL_ATTACHMENT_TITLE: ParagraphStyleSpec(
        FZXBS, TITLE_SIZE_PT, WD_ALIGN_PARAGRAPH.CENTER
    ),
    ParagraphRole.IMPRINT: ParagraphStyleSpec(
        FS, IMPRINT_SIZE_PT, WD_ALIGN_PARAGRAPH.LEFT
    ),
}
