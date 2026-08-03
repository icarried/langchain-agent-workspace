from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from src.agents.batch_resume_review_llm.openai_compatible_api import app


def _payload(response) -> dict:
    data_line = next(
        line for line in response.text.splitlines() if line.startswith("data: ")
    )
    return json.loads(data_line.removeprefix("data: "))


def _call_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _review_request() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "review_resumes",
            "arguments": {
                "resumes": [
                    {
                        "filename": "candidate.txt",
                        "content_base64": base64.b64encode(
                            "姓名：张三\n本科\nPython\n".encode()
                        ).decode(),
                    }
                ],
                "job_description_text": "要求本科，熟悉 Python。",
                "dry_run": True,
            },
        },
    }


def test_http_mcp_requires_unified_tool_permission(monkeypatch) -> None:
    monkeypatch.setenv(
        "AGENT_MCP_TOKENS_JSON",
        json.dumps(
            {
                "resume-token": {
                    "permissions": ["batch-resume-review:review"],
                },
                "wrong-token": {
                    "permissions": ["official-document-formatting:format"],
                },
            }
        ),
    )
    with TestClient(app) as client:
        allowed = client.post(
            "/mcp",
            headers=_call_headers("resume-token"),
            json=_review_request(),
        )
        denied = client.post(
            "/mcp",
            headers=_call_headers("wrong-token"),
            json=_review_request(),
        )

    assert _payload(allowed)["result"]["isError"] is False
    assert _payload(denied)["result"]["isError"] is True
    assert "candidate.txt" not in denied.text
