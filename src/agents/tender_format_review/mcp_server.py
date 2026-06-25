from __future__ import annotations

import argparse
import base64
import binascii
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .service import resolve_workspace_path, review_tender_format


mcp = FastMCP(
    name="tender-format-review",
    instructions=(
        "Use the review_tender_format tool to review Chinese tender .docx files. "
        "Send the .docx file content as base64. Use dry_run=true for quick connectivity, "
        "parsing, and chunking checks before invoking a full review."
    ),
)


@mcp.tool(
    name="review_tender_format",
    description=(
        "Review a Chinese tender .docx file for format and cross-section consistency. "
        "Accepts the .docx file content as base64 and returns a Markdown report."
    ),
)
def review_tender_format_tool(
    docx_base64: str,
    docx_filename: str = "uploaded.docx",
    dry_run: bool = False,
) -> dict[str, Any]:
    content = _decode_docx_base64(docx_base64)
    filename = _safe_docx_filename(docx_filename)
    target_dir = resolve_workspace_path("临时文件/mcp_uploads")
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="review-", dir=target_dir) as temp_dir:
        docx_path = Path(temp_dir) / filename
        docx_path.write_bytes(content)
        result = review_tender_format(docx_path, dry_run=dry_run)

    return {
        "report": result["report"],
        "dry_run": result["dry_run"],
        "chunk_count": result["chunk_count"],
        "filename": filename,
    }


def _decode_docx_base64(docx_base64: str) -> bytes:
    try:
        return base64.b64decode(docx_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("docx_base64 must be valid base64 content.") from exc


def _safe_docx_filename(docx_filename: str) -> str:
    filename = Path(docx_filename).name or "uploaded.docx"
    if not filename.lower().endswith(".docx"):
        filename = f"{filename}.docx"
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tender format review MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport. Use stdio for client-managed on-demand startup; use http for a long-running service.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    parser.add_argument("--port", type=int, default=8002, help="HTTP port")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP endpoint path")
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
