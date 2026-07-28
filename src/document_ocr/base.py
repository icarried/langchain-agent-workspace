from __future__ import annotations

from typing import Protocol


class OCRProvider(Protocol):
    """Extract structured text from one image without owning document storage."""

    def extract_image(self, data: bytes, mime_type: str, *, source: str) -> str: ...
