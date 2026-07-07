from __future__ import annotations

import argparse
import base64
import binascii
import tempfile
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .service import resolve_workspace_path, review_contract


MCP_CONTRACT_EXTENSIONS = {".docx", ".pdf", ".txt"}


mcp = FastMCP(
    name="contract-review",
    instructions=(
        "Use the review_contract tool to review contract files from the client's role, "
        "contract type, and transaction background. Send contract content as base64. "
        "Use dry_run=true for parsing and workflow checks before invoking a full review."
    ),
)


@mcp.tool(
    name="review_contract",
    description="Review a DOCX/PDF/TXT contract and return a Markdown six-dimensional review report.",
)
def review_contract_tool(
    contract_base64: str,
    contract_filename: str = "uploaded.txt",
    client_role: str = "甲方",
    contract_type: str = "",
    transaction_background: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    content = _decode_base64(contract_base64)
    filename = _safe_contract_filename(contract_filename)
    target_dir = resolve_workspace_path("临时文件/mcp_uploads")
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="contract-review-", dir=target_dir) as temp_dir:
        contract_path = Path(temp_dir) / filename
        contract_path.write_bytes(content)
        result = review_contract(
            contract_path,
            client_role=client_role,
            contract_type=contract_type,
            transaction_background=transaction_background,
            dry_run=dry_run,
        )

    return {
        "report": result["report"],
        "dry_run": result["dry_run"],
        "chunk_count": result["chunk_count"],
        "filename": filename,
    }


def _decode_base64(contract_base64: str) -> bytes:
    try:
        return base64.b64decode(contract_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("contract_base64 must be valid base64 content.") from exc


def _safe_contract_filename(contract_filename: str) -> str:
    filename = Path(contract_filename).name or "uploaded.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in MCP_CONTRACT_EXTENSIONS:
        supported = ", ".join(sorted(MCP_CONTRACT_EXTENSIONS))
        raise ValueError(f"unsupported MCP contract file type '{suffix}', supported: {supported}")
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Contract review MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport. Use stdio for client-managed startup; use http for a long-running service.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    parser.add_argument("--port", type=int, default=8009, help="HTTP port")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP endpoint path")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path, show_banner=False)

