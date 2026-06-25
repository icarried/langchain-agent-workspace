from __future__ import annotations

from pathlib import Path

DEFAULT_UNIVERSITY_REFERENCE_DIR = Path(__file__).resolve().parent


def load_university_references(path: str | Path | None = None) -> str:
    reference_path = Path(path) if path else DEFAULT_UNIVERSITY_REFERENCE_DIR
    if not reference_path.exists():
        raise FileNotFoundError(f"university reference path not found: {reference_path}")
    if reference_path.is_file():
        files = [reference_path]
    else:
        files = sorted(
            file
            for file in reference_path.glob("*.md")
            if file.name.lower() != "readme.md"
        )
    if not files:
        raise ValueError(f"no university reference Markdown files found: {reference_path}")
    return "\n\n---\n\n".join(
        f"# 参考文件: {file.name}\n\n{file.read_text(encoding='utf-8-sig')}"
        for file in files
    )
