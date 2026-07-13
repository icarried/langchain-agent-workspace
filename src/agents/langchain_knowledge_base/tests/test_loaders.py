from pathlib import Path

import pytest

from kb_api.rag import loaders
from kb_api.rag.loaders import DocumentRecord, UnsupportedDocumentError, load_document, load_documents


def test_load_document_reads_text_file(tmp_path: Path):
    path = tmp_path / "note.txt"
    path.write_text("hello world", encoding="utf-8")

    document = load_document(path)

    assert document == DocumentRecord(
        page_content="hello world",
        metadata={"source": path.as_posix(), "file_name": "note.txt", "extension": ".txt"},
    )


def test_load_document_reads_markdown_file(tmp_path: Path):
    path = tmp_path / "readme.md"
    path.write_text("# Title\n\nBody", encoding="utf-8")

    document = load_document(path)

    assert document is not None
    assert document.page_content == "# Title\n\nBody"
    assert document.metadata["source"] == path.as_posix()


def test_load_document_returns_none_for_empty_text_file(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")

    assert load_document(path) is None


def test_load_document_raises_for_unknown_extension(tmp_path: Path):
    path = tmp_path / "image.png"
    path.write_text("noop", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentError):
        load_document(path)


def test_load_document_uses_pdf_reader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF")

    class FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _: str):
            self.pages = [FakePage("First page"), FakePage("Second page")]

    def fake_load_pdf_text(_: Path) -> str:
        reader = FakeReader(str(path))
        return "\n\n".join(page.extract_text() for page in reader.pages)

    monkeypatch.setattr(loaders, "_load_pdf_text", fake_load_pdf_text)

    document = load_document(path)

    assert document is not None
    assert document.page_content == "First page\n\nSecond page"


def test_load_document_uses_docx_reader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    path = tmp_path / "memo.docx"
    path.write_bytes(b"PK")

    def fake_load_docx_text(_: Path) -> str:
        return "Heading\nParagraph"

    monkeypatch.setattr(loaders, "_load_docx_text", fake_load_docx_text)

    document = load_document(path)

    assert document is not None
    assert document.page_content == "Heading\nParagraph"


def test_load_documents_skips_unsupported_and_empty_files(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "b.md").write_text(" ", encoding="utf-8")
    (tmp_path / "c.bin").write_text("ignored", encoding="utf-8")

    documents = load_documents(tmp_path)

    assert [document.metadata["file_name"] for document in documents] == ["a.txt"]
