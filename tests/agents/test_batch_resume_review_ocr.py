from __future__ import annotations

from io import BytesIO

from src.agents.batch_resume_review_llm import ocr, resume_loader


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _Reader:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages


def test_workspace_ocr_provider_uses_gpu_stack_defaults(monkeypatch) -> None:
    captured = {}

    class FakeProvider:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def extract_image(self, data, mime_type, *, source):
            captured.update(data=data, mime_type=mime_type, source=source)
            return "姓名：张三\n学历：本科"

    monkeypatch.delenv("BATCH_RESUME_REVIEW_OCR_BASE_URL", raising=False)
    monkeypatch.delenv("BATCH_RESUME_REVIEW_OCR_MODEL", raising=False)
    monkeypatch.setenv("BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS", "45")
    monkeypatch.setattr(ocr, "GPUStackPaddleOCRVL", FakeProvider)

    text = ocr.ocr_image_bytes(b"png", "image/png", source="scan.pdf:page-1")

    assert text == "姓名：张三\n学历：本科"
    assert captured == {
        "model": "paddleocr-vl-1.6",
        "timeout": 45.0,
        "base_url": None,
        "data": b"png",
        "mime_type": "image/png",
        "source": "scan.pdf:page-1",
    }


def test_text_pdf_does_not_call_ocr(monkeypatch) -> None:
    monkeypatch.setattr(
        resume_loader,
        "PdfReader",
        lambda _stream: _Reader([_Page("姓名：张三\n本科\n熟悉 Python 开发")]),
    )
    monkeypatch.setattr(
        resume_loader,
        "ocr_image_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("text PDF must not invoke OCR")
        ),
    )

    elements = resume_loader._load_pdf(BytesIO(b"%PDF"), source="text.pdf")

    assert [item.kind for item in elements] == ["pdf_line", "pdf_line", "pdf_line"]
    assert elements[0].source == "text.pdf:page-1"


def test_scanned_pdf_page_uses_workspace_ocr(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        resume_loader,
        "PdfReader",
        lambda _stream: _Reader([_Page("")]),
    )
    monkeypatch.setattr(
        resume_loader,
        "_render_pdf_page",
        lambda data, page_index, *, source: b"rendered-page",
    )

    def fake_ocr(data, mime_type, *, source):
        calls.append((data, mime_type, source))
        return "姓名：李四\n硕士研究生\n具有项目经验"

    monkeypatch.setattr(resume_loader, "ocr_image_bytes", fake_ocr)

    elements = resume_loader._load_pdf(BytesIO(b"%PDF"), source="scan.pdf")

    assert calls == [(b"rendered-page", "image/png", "scan.pdf:page-1")]
    assert all(item.kind == "ocr_line" for item in elements)
    assert elements[0].text == "姓名：李四"
