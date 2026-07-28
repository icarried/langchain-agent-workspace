"""Reusable OCR providers for document-oriented agents."""

from .base import OCRProvider
from .gpu_stack import GPUStackPaddleOCRVL

__all__ = ["GPUStackPaddleOCRVL", "OCRProvider"]
