"""Deprecated compatibility package for :mod:`batch_resume_review_llm`."""

from __future__ import annotations

import importlib
import sys

from src.agents.batch_resume_review_llm.service import review_resumes


_MODULES = (
    "chunking",
    "cli",
    "doc_converter",
    "graph",
    "llm",
    "mcp_server",
    "ocr",
    "openai_compatible_api",
    "prompts",
    "reference_loader",
    "resume_loader",
    "schemas",
    "security",
    "service",
)

for _name in _MODULES:
    _module = importlib.import_module(f"src.agents.batch_resume_review_llm.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    setattr(sys.modules[__name__], _name, _module)

__all__ = ["review_resumes"]
