from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm

from src.agents.official_document_formatting.formatter import format_docx
from src.agents.official_document_formatting.graph import build_graph
from src.agents.official_document_formatting.service import format_official_document


def _make_company_sample(path: Path) -> Path:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(1)
    section.bottom_margin = Cm(1)
    section.left_margin = Cm(1)
    section.right_margin = Cm(1)
    document.add_paragraph("关于开展测试工作的请示")
    document.add_paragraph("2026年7月29日")
    document.add_paragraph("关于开展测试工作的请示")
    document.add_paragraph("一、主要事项")
    document.add_paragraph("（一）具体安排")
    document.add_paragraph("请各部门按要求完成材料报送。")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "项目"
    table.cell(0, 1).text = "要求"
    table.cell(1, 0).text = "材料"
    table.cell(1, 1).text = "按时报送"
    document.save(path)
    return path


def _east_asia_font(paragraph) -> str | None:
    run = next(run for run in paragraph.runs if run.text.strip())
    fonts = run._r.get_or_add_rPr().rFonts
    return fonts.get(qn("w:eastAsia"))


def test_frozen_formatter_applies_validated_company_rules(tmp_path: Path) -> None:
    source = _make_company_sample(tmp_path / "input.docx")
    output = tmp_path / "output.docx"

    format_docx(source, output)

    formatted = Document(output)
    section = formatted.sections[0]
    assert round(section.top_margin.cm, 1) == 3.7
    assert round(section.bottom_margin.cm, 1) == 3.5
    assert round(section.left_margin.cm, 1) == 2.8
    assert round(section.right_margin.cm, 1) == 2.6
    texts = [paragraph.text for paragraph in formatted.paragraphs if paragraph.text.strip()]
    assert texts == [
        "关于开展测试工作的请示",
        "一、主要事项",
        "（一）具体安排",
        "请各部门按要求完成材料报送。",
    ]
    non_empty = [paragraph for paragraph in formatted.paragraphs if paragraph.text.strip()]
    assert non_empty[0].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert _east_asia_font(non_empty[0]) == "方正小标宋简体"
    assert _east_asia_font(non_empty[1]) == "黑体"
    assert _east_asia_font(non_empty[2]) == "楷体_GB2312"
    assert _east_asia_font(non_empty[3]) == "仿宋_GB2312"
    body_properties = non_empty[3]._p.get_or_add_pPr()
    assert body_properties.ind.get(qn("w:firstLine")) == "640"
    assert body_properties.spacing.get(qn("w:line")) == "560"
    assert body_properties.spacing.get(qn("w:lineRule")) == "exact"
    borders = formatted.tables[0]._tbl.tblPr.find(qn("w:tblBorders"))
    assert borders.find(qn("w:top")).get(qn("w:val")) == "single"
    assert borders.find(qn("w:insideV")).get(qn("w:val")) == "none"


def test_graph_dry_run_validates_without_writing_output(tmp_path: Path) -> None:
    source = _make_company_sample(tmp_path / "input.docx")
    output = tmp_path / "output.docx"

    result = build_graph().invoke(
        {
            "source_path": str(source),
            "output_path": str(output),
            "original_filename": source.name,
            "dry_run": True,
        }
    )

    assert result["result"].dry_run is True
    assert result["result"].content == b""
    assert not output.exists()


def test_service_returns_formatted_docx_bytes_and_keeps_source(tmp_path: Path) -> None:
    source = _make_company_sample(tmp_path / "input.docx")
    original = source.read_bytes()

    result = format_official_document(source)

    assert source.read_bytes() == original
    assert result["filename"] == "input-公文格式化.docx"
    assert result["mime_type"].endswith("wordprocessingml.document")
    assert result["size"] == len(result["content"])
    assert len(result["sha256"]) == 64
    assert result["content"].startswith(b"PK")
    assert result["output_path"] == ""


def test_service_rejects_non_docx_input(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("not a docx", encoding="utf-8")

    try:
        format_official_document(source)
    except ValueError as exc:
        assert "DOCX" in str(exc)
    else:
        raise AssertionError("non-DOCX input should be rejected")

