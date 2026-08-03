from __future__ import annotations

import argparse
import base64
import binascii
import os
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.agents.mcp_auth import authorize_http_mcp
from src.agents.remote_files import is_http_url, read_remote_file, remote_filename

from .service import format_official_document


DEFAULT_MAX_BYTES = 20 * 1024 * 1024


class DocumentUpload(BaseModel):
    filename: str | None = Field(
        default=None,
        description="原始公文文件名；URL 未包含扩展名时必须提供，支持 DOCX 或旧版 DOC",
    )
    content_base64: str | None = Field(
        default=None,
        description="DOCX 或 DOC 文件内容的 base64；与 url 二选一",
    )
    url: str | None = Field(
        default=None,
        description="可由服务端访问的 HTTP(S) 文件 URL（例如 MinIO 预签名 URL）；与 content_base64 二选一",
    )


mcp = FastMCP(
    name="official-document-formatting",
    instructions=(
        "Use format_document to apply deterministic company-approved formatting to one "
        "DOCX or legacy DOC without rewriting its body or table content."
    ),
    mask_error_details=True,
)


@mcp.tool(
    name="format_document",
    description=(
        "Format one DOCX or legacy DOC with the company official-document rules. "
        "Legacy DOC is converted in a temporary directory; output is always DOCX. "
        "The document may be supplied as base64 or as a server-reachable HTTP(S) URL, "
        "such as a MinIO presigned URL. "
        "In dry-run mode, return only the validation report; otherwise also return "
        "the formatted DOCX as base64."
    ),
)
def format_document_tool(
    document: DocumentUpload,
    dry_run: bool = False,
) -> dict[str, Any]:
    authorize_http_mcp("official-document-formatting:format")
    max_bytes = int(
        os.getenv("OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES", str(DEFAULT_MAX_BYTES))
    )
    filename, content = _resolve_document(document, max_bytes=max_bytes)

    with tempfile.TemporaryDirectory(prefix="official-document-formatting-mcp-") as temp_dir:
        source = Path(temp_dir) / filename
        source.write_bytes(content)
        result = format_official_document(
            source,
            original_filename=filename,
            dry_run=dry_run,
        )

    response = {
        "report": result["report"],
        "findings": result["findings"],
        "dry_run": result["dry_run"],
        "filename": result["filename"],
        "mime_type": result["mime_type"],
        "sha256": result["sha256"],
        "size": result["size"],
    }
    if not dry_run:
        response["content_base64"] = base64.b64encode(result["content"]).decode("ascii")
    return response


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 must be valid base64 content") from exc


def _resolve_document(document: DocumentUpload, *, max_bytes: int) -> tuple[str, bytes]:
    has_base64 = document.content_base64 is not None
    has_url = document.url is not None
    if has_base64 == has_url:
        raise ValueError("provide exactly one of content_base64 or url")

    if has_url:
        assert document.url is not None
        if not is_http_url(document.url):
            raise ValueError("url must be an HTTP(S) URL")
        filename = _safe_filename(document.filename or remote_filename(document.url))
        content, _ = read_remote_file(document.url, max_bytes=max_bytes)
    else:
        if not document.filename:
            raise ValueError("filename is required when using content_base64")
        assert document.content_base64 is not None
        filename = _safe_filename(document.filename)
        content = _decode_base64(document.content_base64)

    if len(content) > max_bytes:
        raise ValueError(f"document is larger than {max_bytes} bytes: {filename}")
    return filename, content


def _safe_filename(value: str) -> str:
    filename = Path(value).name
    if not filename or Path(filename).suffix.lower() not in {".doc", ".docx"}:
        raise ValueError("official document MCP upload must be a DOCX or DOC file")
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Official document formatting MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8015)
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
