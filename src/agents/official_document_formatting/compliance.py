"""Static compliance checks and explicit render-verification boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from docx.oxml.ns import qn

from .roles import ParagraphRole, classify_paragraphs
from .standards import (
    BOTTOM_MARGIN_CM,
    EXACT_LINE_SPACING_TWIPS,
    FOOTER_DISTANCE_CM,
    LEFT_MARGIN_CM,
    PAGE_HEIGHT_CM,
    PAGE_WIDTH_CM,
    RIGHT_MARGIN_CM,
    TOP_MARGIN_CM,
)


class ComplianceSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ComplianceFinding:
    severity: ComplianceSeverity
    rule_id: str
    paragraph_index: int | None
    message: str
    verified: bool


def evaluate_compliance(document, *, formatted: bool) -> tuple[ComplianceFinding, ...]:
    """Return failures and rules that require rendering; omit verified passes."""
    findings: list[ComplianceFinding] = []
    if formatted:
        findings.extend(_static_page_findings(document))

    roles = classify_paragraphs(
        [paragraph.text for paragraph in document.paragraphs]
    )
    imprint_index = _first_index(roles, ParagraphRole.IMPRINT)
    signature_index = _first_index(roles, ParagraphRole.SIGNATURE)

    findings.append(
        ComplianceFinding(
            severity=ComplianceSeverity.WARNING,
            rule_id="visual.pagination",
            paragraph_index=None,
            message="每页二十二行、每行二十八字、标题回行和表格跨页需要渲染复核。",
            verified=False,
        )
    )
    if imprint_index is not None:
        findings.append(
            ComplianceFinding(
                severity=ComplianceSeverity.WARNING,
                rule_id="visual.imprint-even-page",
                paragraph_index=imprint_index,
                message="版记是否位于偶数页最后一面需要渲染复核。",
                verified=False,
            )
        )
    if signature_index is not None:
        findings.append(
            ComplianceFinding(
                severity=ComplianceSeverity.WARNING,
                rule_id="visual.seal-position",
                paragraph_index=signature_index,
                message="印章、署名和成文日期的视觉位置需要 Word/WPS 渲染复核。",
                verified=False,
            )
        )
    return tuple(findings)


def compliance_report(
    findings: tuple[ComplianceFinding, ...],
    *,
    dry_run: bool,
) -> str:
    errors = [finding for finding in findings if finding.verified]
    unverified = [finding for finding in findings if not finding.verified]
    if dry_run:
        prefix = "公文格式化 dry-run 已完成：输入 DOCX 有效，未生成输出文件。"
    else:
        prefix = "公文格式化完成，已生成新的 DOCX，正文和表格内容未改写。"
    parts = [prefix]
    if errors:
        parts.append(f"静态检查发现 {len(errors)} 项不符合项。")
    elif not dry_run:
        parts.append("页面、字体、字号、缩进、行距和动态页码等静态规则已通过。")
    if unverified:
        summary = "；".join(finding.message for finding in unverified)
        parts.append(f"另有 {len(unverified)} 项未验证：{summary}")
    return "".join(parts)


def _static_page_findings(document) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for section_index, section in enumerate(document.sections):
        actual = (
            round(section.page_width.cm, 1),
            round(section.page_height.cm, 1),
            round(section.top_margin.cm, 1),
            round(section.bottom_margin.cm, 1),
            round(section.left_margin.cm, 1),
            round(section.right_margin.cm, 1),
            round(section.footer_distance.cm, 1),
        )
        expected = (
            PAGE_WIDTH_CM,
            PAGE_HEIGHT_CM,
            TOP_MARGIN_CM,
            BOTTOM_MARGIN_CM,
            LEFT_MARGIN_CM,
            RIGHT_MARGIN_CM,
            FOOTER_DISTANCE_CM,
        )
        if actual != expected:
            findings.append(
                _static_error(
                    "page.geometry",
                    f"第 {section_index + 1} 节页面尺寸或页边距不符合规范。",
                )
            )
        grid = section._sectPr.find(qn("w:docGrid"))
        if (
            grid is None
            or grid.get(qn("w:type")) != "linesAndChars"
            or grid.get(qn("w:linePitch")) != str(EXACT_LINE_SPACING_TWIPS)
        ):
            findings.append(
                _static_error(
                    "page.grid",
                    f"第 {section_index + 1} 节页面网格不符合规范。",
                )
            )
        if (
            "PAGE" not in section.footer._element.xml
            or "PAGE" not in section.even_page_footer._element.xml
        ):
            findings.append(
                _static_error(
                    "page.number",
                    f"第 {section_index + 1} 节缺少奇偶页动态页码。",
                )
            )
    return findings


def _static_error(rule_id: str, message: str) -> ComplianceFinding:
    return ComplianceFinding(
        severity=ComplianceSeverity.ERROR,
        rule_id=rule_id,
        paragraph_index=None,
        message=message,
        verified=True,
    )


def _first_index(
    roles: list[ParagraphRole],
    expected: ParagraphRole,
) -> int | None:
    return next((index for index, role in enumerate(roles) if role is expected), None)
