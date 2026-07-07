from __future__ import annotations

import argparse
import base64
import binascii
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .service import resolve_workspace_path, screen_resumes


MCP_RESUME_EXTENSIONS = {".docx", ".pdf", ".txt"}


mcp = FastMCP(
    name="smart-resume-screening",
    instructions=(
        "Use the screen_resumes tool to rank resume files by structured hiring criteria. "
        "Send resume contents as base64. Use dry_run=true before invoking a full LLM report."
    ),
)


@mcp.tool(
    name="screen_resumes",
    description="Screen multiple DOCX/PDF/TXT resumes with structured conditions and return a Markdown report.",
)
def screen_resumes_tool(
    resumes: list[dict[str, str]],
    job_description_text: str = "",
    position_name: str = "",
    department: str = "",
    level_range: str = "",
    hard_conditions: list[str] | None = None,
    bonus_conditions: list[str] | None = None,
    reject_conditions: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    target_dir = resolve_workspace_path("临时文件/mcp_uploads")
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smart-resume-screening-", dir=target_dir) as temp_dir:
        resume_paths = []
        for item in resumes:
            filename = _safe_resume_filename(item.get("filename", "uploaded.txt"))
            content = _decode_base64(item.get("content_base64", ""))
            path = Path(temp_dir) / filename
            path.write_bytes(content)
            resume_paths.append(path)
        result = screen_resumes(
            resume_paths,
            job_description_text=job_description_text,
            position_name=position_name,
            department=department,
            level_range=level_range,
            hard_conditions=hard_conditions or [],
            bonus_conditions=bonus_conditions or [],
            reject_conditions=reject_conditions or [],
            dry_run=dry_run,
        )
    return {
        "report": result["report"],
        "dry_run": result["dry_run"],
        "candidate_count": result["candidate_count"],
        "scores": result["scores"],
    }


def _decode_base64(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 must be valid base64 content.") from exc


def _safe_resume_filename(filename: str) -> str:
    safe = Path(filename).name or "uploaded.txt"
    suffix = Path(safe).suffix.lower()
    if suffix not in MCP_RESUME_EXTENSIONS:
        supported = ", ".join(sorted(MCP_RESUME_EXTENSIONS))
        raise ValueError(f"unsupported MCP resume file type '{suffix}', supported: {supported}")
    return safe


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart resume screening MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport. Use stdio for client-managed startup; use http for a long-running service.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    parser.add_argument("--port", type=int, default=8011, help="HTTP port")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP endpoint path")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path, show_banner=False)

