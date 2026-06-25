from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport


def main() -> None:
    parser = argparse.ArgumentParser(description="Call tender-format-review over MCP")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--url", default="http://127.0.0.1:8002/mcp")
    parser.add_argument("--docx-path", default="./临时文件/仅包含一行文字的文件.docx")
    parser.add_argument("--save-report", help="Optional path to save the returned Markdown report")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    result = asyncio.run(_call(args.transport, args.url, args.docx_path, args.dry_run))
    if args.save_report:
        report_path = Path(args.save_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(result["report"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def _call(
    transport_name: str,
    url: str,
    docx_path: str,
    dry_run: bool,
) -> dict[str, Any]:
    if transport_name == "stdio":
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "src.agents.tender_format_review.mcp_server"],
            cwd=str(_workspace_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    else:
        transport = StreamableHttpTransport(url)

    async with Client(transport) as client:
        tools = await client.list_tools()
        path = Path(docx_path)
        arguments: dict[str, Any] = {
            "docx_filename": path.name,
            "docx_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            "dry_run": dry_run,
        }

        result = await client.call_tool(
            "review_tender_format",
            arguments,
        )
        return {
            "tools": [tool.name for tool in tools],
            "report": result.data["report"],
            "dry_run": result.data["dry_run"],
            "chunk_count": result.data["chunk_count"],
            "filename": result.data["filename"],
        }


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    main()
