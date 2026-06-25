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
    parser = argparse.ArgumentParser(description="Call batch-resume-review over MCP")
    parser.add_argument("resume_paths", nargs="+", help="PDF, DOC, DOCX, MD, or TXT resume files")
    parser.add_argument("--job-description", required=True, help="UTF-8 job-description text file")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--url", default="http://127.0.0.1:8005/mcp")
    parser.add_argument("--save-report", help="Optional Markdown report output path")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    result = asyncio.run(
        _call(
            args.transport,
            args.url,
            [Path(path) for path in args.resume_paths],
            Path(args.job_description),
            args.dry_run,
        )
    )
    if args.save_report:
        output = Path(args.save_report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result["report"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def _call(
    transport_name: str,
    url: str,
    resume_paths: list[Path],
    job_description_path: Path,
    dry_run: bool,
) -> dict[str, Any]:
    if transport_name == "stdio":
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "batch_resume_review.mcp_server"],
            cwd=str(Path.cwd()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    else:
        transport = StreamableHttpTransport(url)

    uploads = [
        {
            "filename": path.name,
            "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
        for path in resume_paths
    ]
    arguments = {
        "resumes": uploads,
        "job_description_text": job_description_path.read_text(encoding="utf-8-sig"),
        "dry_run": dry_run,
    }
    async with Client(transport) as client:
        tools = await client.list_tools()
        result = await client.call_tool("review_resumes", arguments)
    return {"tools": [tool.name for tool in tools], **result.data}


if __name__ == "__main__":
    main()
