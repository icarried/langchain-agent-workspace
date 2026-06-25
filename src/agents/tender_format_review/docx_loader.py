from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .schemas import DocumentElement

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def load_docx_elements(path: str | Path) -> list[DocumentElement]:
    """Extract paragraphs and tables from a docx file with only stdlib OOXML parsing."""
    docx_path = Path(path)
    if not docx_path.exists():
        raise FileNotFoundError(f"docx not found: {docx_path}")
    if docx_path.suffix.lower() != ".docx":
        raise ValueError(f"expected .docx file, got: {docx_path}")

    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ET.fromstring(document_xml)
    body = root.find("w:body", WORD_NS)
    if body is None:
        return []

    elements: list[DocumentElement] = []
    for child in list(body):
        tag = _local_name(child.tag)
        if tag == "p":
            text = _paragraph_text(child)
            if text:
                elements.append(
                    DocumentElement(
                        index=len(elements),
                        kind="paragraph",
                        text=text,
                        style=_paragraph_style(child),
                    )
                )
        elif tag == "tbl":
            rows = _table_rows(child)
            if rows:
                elements.append(
                    DocumentElement(
                        index=len(elements),
                        kind="table",
                        text="\n".join(rows),
                        style="table",
                    )
                )
    return elements


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        name = _local_name(node.tag)
        if name == "t" and node.text:
            parts.append(node.text)
        elif name in {"tab", "br", "cr"}:
            parts.append("\t" if name == "tab" else "\n")
    return _normalize("".join(parts))


def _paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find("w:pPr/w:pStyle", WORD_NS)
    if style is None:
        return ""
    return style.attrib.get(f"{{{WORD_NS['w']}}}val", "")


def _table_rows(table: ET.Element) -> list[str]:
    rows: list[str] = []
    for row in table.findall(".//w:tr", WORD_NS):
        cells: list[str] = []
        for cell in row.findall("w:tc", WORD_NS):
            texts = [_paragraph_text(p) for p in cell.findall(".//w:p", WORD_NS)]
            cells.append(_normalize(" ".join(t for t in texts if t)))
        line = " | ".join(cells).strip()
        if line:
            rows.append(line)
    return rows


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
