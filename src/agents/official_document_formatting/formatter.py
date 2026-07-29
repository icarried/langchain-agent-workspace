"""Company-validated DOCX formatter.

The formatting decisions in :func:`format_docx` are intentionally kept aligned
with the validated script supplied in ``临时文件/公文格式化配置``. Agent and
deployment concerns belong outside this module.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

FZXBS = "方正小标宋简体"
HEI = "黑体"
KAI = "楷体_GB2312"
FS = "仿宋_GB2312"
BLACK = RGBColor(0, 0, 0)
PT22 = 22
PT16 = 16


def set_font(run, name, size):
    rpr = run._element.find(qn("w:rPr"))
    if rpr is None:
        rpr = parse_xml(f'<w:rPr {nsdecls("w")}/>')
        run._element.insert(0, rpr)
    for tag in ["w:rFonts", "w:sz", "w:szCs", "w:color", "w:b", "w:bCs"]:
        for old in rpr.findall(qn(tag)):
            rpr.remove(old)
    rpr.append(
        parse_xml(
            f'<w:rFonts {nsdecls("w")} '
            f'w:eastAsia="{name}" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
        )
    )
    rpr.append(parse_xml(f'<w:sz {nsdecls("w")} w:val="{size * 2}"/>'))
    rpr.append(parse_xml(f'<w:szCs {nsdecls("w")} w:val="{size * 2}"/>'))
    rpr.append(parse_xml(f'<w:color {nsdecls("w")} w:val="000000"/>'))


def format_docx(src: str | Path, dst: str | Path) -> None:
    doc = Document(src)

    for sect in doc.sections:
        sect.top_margin = Cm(3.7)
        sect.bottom_margin = Cm(3.5)
        sect.left_margin = Cm(2.8)
        sect.right_margin = Cm(2.6)

    for para_idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        para.style = doc.styles["Normal"]

        ppr = para._p.find(qn("w:pPr"))
        if ppr is None:
            ppr = parse_xml(f'<w:pPr {nsdecls("w")}/>')
            para._p.insert(0, ppr)
        for tag in ["w:pBdr", "w:bdr", "w:shd"]:
            for el in ppr.findall(qn(tag)):
                ppr.remove(el)
        for old in ppr.findall(qn("w:spacing")):
            ppr.remove(old)
        ppr.append(
            parse_xml(
                f'<w:spacing {nsdecls("w")} w:line="560" w:lineRule="exact"/>'
            )
        )

        is_title = False
        if (
            re.match(r"^关于.*请示", text)
            or re.match(r"^概念验证中心", text)
            or re.match(r"^中国—东盟", text)
            or re.match(r"^面向能源行业", text)
            or re.match(r"^工业人工智能联合实验室", text)
            or re.match(r"^智启能源新未来", text)
        ):
            is_title = True
        if (
            not is_title
            and para_idx == 0
            and len(text) <= 50
            and not text.endswith(("。", "，", "；", "：", "了", "的"))
        ):
            is_title = True

        if is_title:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                set_font(run, FZXBS, PT22)
        elif re.match(r"^[一二三四五六七八九十]、", text):
            for run in para.runs:
                set_font(run, HEI, PT16)
        elif re.match(r"^（[一二三四五六七八九十]）", text) or re.match(
            r"^方式[一二]", text
        ):
            for run in para.runs:
                set_font(run, KAI, PT16)
        else:
            for old in ppr.findall(qn("w:ind")):
                ppr.remove(old)
            ppr.append(parse_xml(f'<w:ind {nsdecls("w")} w:firstLine="640"/>'))
            for run in para.runs:
                set_font(run, FS, PT16)

    for table in doc.tables:
        tbl_pr = table._tbl.tblPr
        if tbl_pr is None:
            tbl_pr = parse_xml(f'<w:tblPr {nsdecls("w")}/>')
            table._tbl.insert(0, tbl_pr)
        for old_border in tbl_pr.findall(qn("w:tblBorders")):
            tbl_pr.remove(old_border)
        tbl_pr.append(
            parse_xml(
                f'<w:tblBorders {nsdecls("w")}>'
                '  <w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
                '  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
                '  <w:left w:val="none" w:sz="0" w:space="0" w:color="000000"/>'
                '  <w:right w:val="none" w:sz="0" w:space="0" w:color="000000"/>'
                '  <w:insideH w:val="none" w:sz="0" w:space="0" w:color="000000"/>'
                '  <w:insideV w:val="none" w:sz="0" w:space="0" w:color="000000"/>'
                "</w:tblBorders>"
            )
        )
        for row_idx, row in enumerate(table.rows):
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    paragraph.paragraph_format.space_before = Pt(2)
                    paragraph.paragraph_format.space_after = Pt(2)
                    for run in paragraph.runs:
                        set_font(run, FS, 12)
            if row_idx == 0:
                for cell in row.cells:
                    tc_pr = cell._tc.get_or_add_tcPr()
                    for old_border in tc_pr.findall(qn("w:tcBorders")):
                        tc_pr.remove(old_border)
                    tc_pr.append(
                        parse_xml(
                            f'<w:tcBorders {nsdecls("w")}>'
                            '  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
                            "</w:tcBorders>"
                        )
                    )

    doc.save(dst)
    doc2 = Document(dst)
    to_remove = []
    seen = set()
    for index, paragraph in enumerate(doc2.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        if index < 3 and re.match(r"\d{4}年\d{1,2}月\d{1,2}日$", text):
            to_remove.append(paragraph._p)
            continue
        if any(keyword in text for keyword in ["关于", "概念验证", "智启能源"]):
            if text in seen:
                to_remove.append(paragraph._p)
            seen.add(text)
    for paragraph in to_remove:
        paragraph.getparent().remove(paragraph)
    doc2.save(dst)

