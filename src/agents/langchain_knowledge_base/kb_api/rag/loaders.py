from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class UnsupportedDocumentError(ValueError):
    """Raised when a file extension does not map to a supported loader."""


@dataclass(slots=True)
class DocumentRecord:
    page_content: str
    metadata: dict[str, object] = field(default_factory=dict)


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".txt"}


def is_supported_document(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def load_document(path: str | Path) -> DocumentRecord | None:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(f"Unsupported document extension: {suffix or '<none>'}")

    if suffix == ".pdf":
        text = _load_pdf_text(file_path)
    elif suffix == ".docx":
        text = _load_docx_text(file_path)
    else:
        text = _load_text_file(file_path)

    normalized = text.strip()
    if not normalized:
        return None

    return DocumentRecord(
        page_content=normalized,
        metadata={
            "source": file_path.as_posix(),
            "file_name": file_path.name,
            "extension": suffix,
        },
    )


def iter_document_paths(root: str | Path) -> Iterable[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []

    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file()
    )


def load_documents(root: str | Path) -> list[DocumentRecord]:
    documents: list[DocumentRecord] = []
    for path in iter_document_paths(root):
        if not is_supported_document(path):
            continue
        document = load_document(path)
        if document is not None:
            documents.append(document)
    return documents


def _load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(part.strip() for part in pages if part and part.strip())


def _load_docx_text(path: Path) -> str:
    from docx import Document as DocxDocument

    document = DocxDocument(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    return "\n".join(part for part in paragraphs if part)
