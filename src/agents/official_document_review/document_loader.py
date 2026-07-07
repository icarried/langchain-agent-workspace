from __future__ import annotations

from pathlib import Path

from docx import Document
from pypdf import PdfReader

from .schemas import DocumentElement


SUPPORTED_EXTENSIONS = {".docx", ".md", ".pdf", ".txt"}


def load_document_elements(path: str | Path) -> list[DocumentElement]:
    document_path = Path(path)
    if not document_path.exists():
        raise FileNotFoundError(f"official document file not found: {document_path}")

    suffix = document_path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return _load_text(document_path)
    if suffix == ".docx":
        return _load_docx(document_path)
    if suffix == ".pdf":
        return _load_pdf(document_path)

    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise ValueError(f"unsupported official document file type '{suffix}', supported: {supported}")


def _load_text(path: Path) -> list[DocumentElement]:
    text = path.read_text(encoding="utf-8-sig")
    return _elements_from_lines(text.splitlines(), kind="paragraph", source=path.name)


def _load_docx(path: Path) -> list[DocumentElement]:
    document = Document(path)
    elements: list[DocumentElement] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        elements.append(
            DocumentElement(
                index=len(elements) + 1,
                kind="paragraph",
                text=text,
                source=path.name,
                style=paragraph.style.name if paragraph.style else "",
            )
        )
    return elements


def _load_pdf(path: Path) -> list[DocumentElement]:
    reader = PdfReader(str(path))
    elements: list[DocumentElement] = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        for line in _clean_lines(page_text.splitlines()):
            elements.append(
                DocumentElement(
                    index=len(elements) + 1,
                    kind="pdf_line",
                    text=line,
                    source=f"{path.name}:page-{page_number}",
                )
            )
    if not elements:
        raise ValueError("PDF has no extractable text; scanned-image OCR is not supported in v1.")
    return elements


def _elements_from_lines(lines: list[str], *, kind: str, source: str) -> list[DocumentElement]:
    return [
        DocumentElement(index=index, kind=kind, text=line, source=source)
        for index, line in enumerate(_clean_lines(lines), start=1)
    ]


def _clean_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]

