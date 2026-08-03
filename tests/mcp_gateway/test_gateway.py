from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastmcp import Client, FastMCP

from src.mcp_gateway.app import build_mcp_gateway
from src.mcp_gateway.registry import McpBackendSpec, load_mcp_backends


ROOT = Path(__file__).resolve().parents[2]


def test_registry_defines_one_public_aggregator_and_three_backends() -> None:
    payload = json.loads(
        (ROOT / "config" / "agent_gateway.json").read_text(encoding="utf-8")
    )
    assert [item["id"] for item in payload["mcp_servers"]] == [
        "workspace-mcp-gateway"
    ]
    assert [item.id for item in load_mcp_backends()] == [
        "department-knowledge-base",
        "batch-resume-review",
        "official-document-formatting",
    ]

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "ports" not in services["mcp-gateway"]
    assert set(services["mcp-gateway"]["depends_on"]) == {
        "department-knowledge-base",
        "batch-resume-review",
        "official-document-formatting",
    }
    assert services["gateway"]["depends_on"]["mcp-gateway"]["condition"] == (
        "service_healthy"
    )
    assert [name for name, service in services.items() if "ports" in service] == [
        "gateway"
    ]


@pytest.mark.asyncio
async def test_composition_exposes_stable_namespaced_tools() -> None:
    department = FastMCP("department")
    batch = FastMCP("batch")
    official = FastMCP("official")

    @department.tool(name="department_kb_query")
    def query(question: str) -> str:
        return question

    @batch.tool(name="review_resumes")
    def review() -> str:
        return "reviewed"

    @official.tool(name="format_document")
    def format_document() -> str:
        return "formatted"

    servers = {
        "memory://department": department,
        "memory://batch": batch,
        "memory://official": official,
    }
    gateway = build_mcp_gateway(
        [
            McpBackendSpec("department", "memory://department"),
            McpBackendSpec(
                "batch",
                "memory://batch",
                prefix="batch_resume",
                tool_names={"review_resumes": "review"},
            ),
            McpBackendSpec(
                "official",
                "memory://official",
                prefix="official_document",
                tool_names={"format_document": "format"},
            ),
        ],
        proxy_factory=lambda upstream: servers[upstream],
    )

    async with Client(gateway) as client:
        tools = {tool.name for tool in await client.list_tools()}
        assert tools == {
            "department_kb_query",
            "batch_resume_review",
            "official_document_format",
        }
        assert (await client.call_tool("batch_resume_review", {})).data == "reviewed"
        assert (
            await client.call_tool("official_document_format", {})
        ).data == "formatted"
