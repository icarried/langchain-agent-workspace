from __future__ import annotations

import argparse
import base64
import binascii
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .service import resolve_workspace_path, review_official_document


MCP_DOCUMENT_EXTENSIONS = {".docx", ".pdf", ".txt"}


mcp = FastMCP(
    name="official-document-review",
    instructions=(
        "Use the review_official_document tool to check official document format. "
        "Send document content as base64. Use dry_run=true for parsing and deterministic checks."
    ),
)


@mcp.tool(
    name="review_official_document",
    description="Check a DOCX/PDF/TXT official document and return a Markdown format review report.",
)
def review_official_document_tool(
    document_base64: str,
    document_filename: str = "uploaded.txt",
    document_type: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    content = _decode_base64(document_base64)
    filename = _safe_document_filename(document_filename)
    target_dir = resolve_workspace_path("临时文件/mcp_uploads")
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="official-document-review-", dir=target_dir) as temp_dir:
        document_path = Path(temp_dir) / filename
        document_path.write_bytes(content)
        result = review_official_document(
            document_path,
            document_type=document_type,
            dry_run=dry_run,
        )

    return {
        "report": result["report"],
        "dry_run": result["dry_run"],
        "finding_count": result["finding_count"],
        "filename": filename,
    }


def _decode_base64(document_base64: str) -> bytes:
    try:
        return base64.b64decode(document_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("document_base64 must be valid base64 content.") from exc


def _safe_document_filename(document_filename: str) -> str:
    filename = Path(document_filename).name or "uploaded.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in MCP_DOCUMENT_EXTENSIONS:
        supported = ", ".join(sorted(MCP_DOCUMENT_EXTENSIONS))
        raise ValueError(f"unsupported MCP official document file type '{suffix}', supported: {supported}")
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Official document review MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport. Use stdio for client-managed startup; use http for a long-running service.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    parser.add_argument("--port", type=int, default=8010, help="HTTP port")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP endpoint path")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path, show_banner=False)

