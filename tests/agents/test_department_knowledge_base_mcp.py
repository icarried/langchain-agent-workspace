from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.agents.department_knowledge_base import openai_compatible_api as api


TOKEN = "marketing-read-token"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-11-25",
}


def _payload(response) -> dict:
    data_line = next(
        line for line in response.text.splitlines() if line.startswith("data: ")
    )
    return json.loads(data_line.removeprefix("data: "))


def _request(method: str, *, request_id: int, params: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


def test_mcp_tools_bind_department_at_connection_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "DEPARTMENT_KB_MCP_TOKENS_JSON",
        json.dumps(
            {
                TOKEN: {
                    "knowledge_id": "marketing",
                    "permissions": ["kb:list", "kb:query", "kb:import-status"],
                }
            }
        ),
    )
    with TestClient(api.app) as client:
        tools = _payload(
            client.post(
                "/mcp",
                headers=HEADERS,
                json=_request("tools/list", request_id=1),
            )
        )["result"]["tools"]
        listed = _payload(
            client.post(
                "/mcp",
                headers=HEADERS,
                json=_request(
                    "tools/call",
                    request_id=2,
                    params={
                        "name": "department_kb_list_spaces",
                        "arguments": {},
                    },
                ),
            )
        )

    assert all(
        "knowledge_id" not in tool["inputSchema"].get("properties", {})
        for tool in tools
    )
    assert listed["result"]["structuredContent"] == {
        "knowledge_space": {
            "knowledge_id": "marketing",
            "display_name": "市场营销部",
        }
    }


def test_mcp_accepts_unified_token_scope(monkeypatch) -> None:
    monkeypatch.delenv("DEPARTMENT_KB_MCP_TOKENS_JSON", raising=False)
    monkeypatch.setenv(
        "AGENT_MCP_TOKENS_JSON",
        json.dumps(
            {
                TOKEN: {
                    "knowledge_id": "marketing",
                    "permissions": ["department-kb:list"],
                }
            }
        ),
    )
    with TestClient(api.app) as client:
        response = client.post(
            "/mcp",
            headers=HEADERS,
            json=_request(
                "tools/call",
                request_id=1,
                params={
                    "name": "department_kb_list_spaces",
                    "arguments": {},
                },
            ),
        )

    assert _payload(response)["result"]["structuredContent"]["knowledge_space"] == {
        "knowledge_id": "marketing",
        "display_name": "市场营销部",
    }


def test_mcp_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv(
        "DEPARTMENT_KB_MCP_TOKENS_JSON",
        json.dumps(
            {
                TOKEN: {
                    "knowledge_id": "marketing",
                    "permissions": ["kb:list"],
                }
            }
        ),
    )
    with TestClient(api.app) as client:
        response = client.post(
            "/mcp",
            headers={key: value for key, value in HEADERS.items() if key != "Authorization"},
            json=_request(
                "tools/call",
                request_id=1,
                params={
                    "name": "department_kb_list_spaces",
                    "arguments": {},
                },
            ),
        )

    payload = _payload(response)
    assert payload["result"]["isError"] is True
    assert "market" not in response.text


def test_mcp_query_uses_token_department(monkeypatch) -> None:
    monkeypatch.setenv(
        "DEPARTMENT_KB_MCP_TOKENS_JSON",
        json.dumps(
            {
                TOKEN: {
                    "knowledge_id": "marketing",
                    "permissions": ["kb:query"],
                }
            }
        ),
    )
    called = {}

    def fake_query(department, question, *, top_k, has_attachments):
        called.update(
            knowledge_id=department.knowledge_id,
            question=question,
            top_k=top_k,
            has_attachments=has_attachments,
        )
        from src.agents.department_knowledge_base.schemas import AgentResult, Intent

        return AgentResult(
            intent=Intent.QUERY,
            content="answer",
            knowledge_id=department.knowledge_id,
            department=department.display_name,
        )

    monkeypatch.setattr(api.agent.runtime, "query", fake_query)
    with TestClient(api.app) as client:
        response = client.post(
            "/mcp",
            headers=HEADERS,
            json=_request(
                "tools/call",
                request_id=1,
                params={
                    "name": "department_kb_query",
                    "arguments": {"question": "市场制度是什么？", "top_k": 3},
                },
            ),
        )

    assert _payload(response)["result"]["isError"] is False
    assert called == {
        "knowledge_id": "marketing",
        "question": "市场制度是什么？",
        "top_k": 3,
        "has_attachments": False,
    }
