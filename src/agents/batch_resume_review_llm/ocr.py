from __future__ import annotations

import os

from src.document_ocr.gpu_stack import GPUStackPaddleOCRVL, OCRRequestError
from src.model_gateway import GPU_STACK_OCR_MODEL


DEFAULT_OCR_MODEL = GPU_STACK_OCR_MODEL
DEFAULT_OCR_TIMEOUT_SECONDS = 180.0


def ocr_image_bytes(data: bytes, mime_type: str, *, source: str) -> str:
    """Extract one resume page through the workspace shared OCR provider."""
    if not data:
        raise ValueError(f"OCR input is empty for '{source}'")
    timeout = _positive_timeout()
    provider = GPUStackPaddleOCRVL(
        model=(
            os.getenv("BATCH_RESUME_REVIEW_OCR_MODEL", "").strip()
            or DEFAULT_OCR_MODEL
        ),
        timeout=timeout,
        base_url=(
            os.getenv("BATCH_RESUME_REVIEW_OCR_BASE_URL", "").strip() or None
        ),
    )
    try:
        text = provider.extract_image(data, mime_type, source=source)
    except (OCRRequestError, RuntimeError, ValueError) as exc:
        raise ValueError(f"workspace OCR failed for '{source}': {exc}") from exc
    if not text.strip():
        raise ValueError(f"workspace OCR returned no text for '{source}'")
    return text.strip()


def _positive_timeout() -> float:
    raw = os.getenv(
        "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS",
        str(DEFAULT_OCR_TIMEOUT_SECONDS),
    )
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise ValueError(
            "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS must be a positive number"
        ) from exc
    if timeout <= 0:
        raise ValueError(
            "BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS must be a positive number"
        )
    return timeout
