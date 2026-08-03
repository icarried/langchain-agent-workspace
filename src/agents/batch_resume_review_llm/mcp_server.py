from __future__ import annotations

import argparse
import base64
import binascii
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.agents.mcp_auth import authorize_http_mcp

from .service import MAX_RESUMES, review_resumes

MCP_RESUME_EXTENSIONS = {".doc", ".docx", ".md", ".pdf", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024


class ResumeUpload(BaseModel):
    filename: str = Field(..., description="原始简历文件名，支持 DOC/DOCX/PDF/MD/TXT")
    content_base64: str = Field(..., description="简历文件内容的 base64")


mcp = FastMCP(
    name="batch-resume-review-llm",
    instructions=(
        "Use review_resumes to screen multiple DOC/DOCX/PDF/MD/TXT resumes against one job description. "
        "Prompt-injection and hard-requirement failures are excluded with reasons. Candidates "
        "requiring human confirmation may retain a score and ranking with an explicit review flag."
    ),
)


@mcp.tool(
    name="review_resumes",
    description=(
        "Review multiple resume uploads against job-description text, exclude candidates that "
        "contain prompt injection or clearly fail hard requirements, score eligible candidates, "
        "and separately flag candidates requiring human confirmation."
    ),
)
def review_resumes_tool(
    resumes: list[ResumeUpload],
    job_description_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    authorize_http_mcp("batch-resume-review:review")
    if not resumes:
        raise ValueError("at least one resume is required")
    if len(resumes) > MAX_RESUMES:
        raise ValueError(f"a batch can contain at most {MAX_RESUMES} resumes")
    if not job_description_text.strip():
        raise ValueError("job_description_text must not be empty")

    with tempfile.TemporaryDirectory(prefix="batch-resume-review-llm-") as temp_dir:
        paths = _write_uploads(resumes, Path(temp_dir))
        result = review_resumes(
            paths,
            job_description_text=job_description_text,
            dry_run=dry_run,
        )

    return {
        "report": result["report"],
        "report_html": result["report_html"],
        "dry_run": result["dry_run"],
        "candidate_count": result["candidate_count"],
        "qualified_count": result["qualified_count"],
        "excluded_count": result["excluded_count"],
        "pending_count": result["pending_count"],
        "ranking": result["ranking"],
        "excluded": result["excluded"],
        "pending": result["pending"],
        "filenames": [upload.filename for upload in resumes],
    }


def _write_uploads(resumes: list[ResumeUpload], directory: Path) -> list[Path]:
    paths = []
    filenames = set()
    for upload in resumes:
        filename = _safe_filename(upload.filename)
        key = filename.lower()
        if key in filenames:
            raise ValueError(f"duplicate resume filename: {filename}")
        filenames.add(key)
        content = _decode_base64(upload.content_base64)
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(
                f"resume file is larger than {MAX_FILE_BYTES} bytes: {filename}"
            )
        path = directory / filename
        path.write_bytes(content)
        paths.append(path)
    return paths


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 must be valid base64 content") from exc


def _safe_filename(value: str) -> str:
    filename = Path(value).name
    if not filename:
        raise ValueError("resume filename must not be empty")
    suffix = Path(filename).suffix.lower()
    if suffix not in MCP_RESUME_EXTENSIONS:
        supported = ", ".join(sorted(MCP_RESUME_EXTENSIONS))
        raise ValueError(
            f"unsupported MCP resume file type '{suffix}', supported: {supported}"
        )
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch resume review MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8005)
    parser.add_argument("--path", default="/mcp")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            show_banner=False,
        )
