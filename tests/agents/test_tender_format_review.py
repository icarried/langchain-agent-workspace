from __future__ import annotations

import base64
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from src.agents.tender_format_review.api import app
from src.agents.tender_format_review.chunking import chunk_elements
from src.agents.tender_format_review.docx_loader import load_docx_elements
from src.agents.tender_format_review.graph import build_graph
from src.agents.tender_format_review.llm import create_chat_model
from src.agents.tender_format_review.mcp_server import mcp
from src.agents.tender_format_review.service import DEFAULT_REVIEW_GUIDE_PATH, review_tender_format


def test_docx_loader_extracts_paragraphs_and_tables(tmp_path: Path) -> None:
    docx = _make_minimal_docx(tmp_path)

    elements = load_docx_elements(docx)

    assert [e.kind for e in elements] == ["paragraph", "paragraph", "table"]
    assert elements[0].text == "第一章 招标公告"
    assert "项目名称 | 工期" in elements[2].text


def test_chunk_elements_splits_by_heading(tmp_path: Path) -> None:
    elements = load_docx_elements(_make_minimal_docx(tmp_path))

    chunks = chunk_elements(elements, max_chars=2200)

    assert chunks
    assert chunks[0].chunk_id == "chunk-001"
    assert "第一章 招标公告" in chunks[0].title


def test_graph_dry_run_creates_report(tmp_path: Path) -> None:
    docx = _make_minimal_docx(tmp_path)
    output = tmp_path / "report.md"
    graph = build_graph()

    result = graph.invoke(
        {
            "docx_path": str(docx),
            "output_path": str(output),
            "dry_run": True,
            "provider": "deepseek",
        }
    )

    assert "dry-run 报告" in result["final_report"]
    assert output.exists()


def test_graph_loads_review_guide_siblings_by_default(tmp_path: Path) -> None:
    docx = _make_minimal_docx(tmp_path)
    graph = build_graph()

    result = graph.invoke(
        {
            "docx_path": str(docx),
            "review_guide_path": str(DEFAULT_REVIEW_GUIDE_PATH),
            "dry_run": True,
            "provider": "deepseek",
        }
    )

    assert "招标文件修订经验指南" in result["review_guide"]
    assert "广西投资集团采购管理办法审查依据" in result["review_guide"]


def test_service_dry_run_with_workspace_relative_docx() -> None:
    result = review_tender_format(
        "./临时文件/仅包含一行文字的文件.docx",
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["chunk_count"] >= 1
    assert "dry-run 报告" in result["report"]


def test_api_review_dry_run_with_workspace_relative_docx() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.post(
        "/review",
        json={
            "docx_path": "./临时文件/仅包含一行文字的文件.docx",
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["chunk_count"] >= 1
    assert "dry-run 报告" in data["report"]


@pytest.mark.asyncio
async def test_mcp_review_tool_accepts_base64_docx_upload(tmp_path: Path) -> None:
    docx = _make_minimal_docx(tmp_path)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert any(tool.name == "review_tender_format" for tool in tools)

        result = await client.call_tool(
            "review_tender_format",
            {
                "docx_base64": base64.b64encode(docx.read_bytes()).decode("ascii"),
                "docx_filename": "client-upload.docx",
                "dry_run": True,
            },
        )

    assert result.data["dry_run"] is True
    assert result.data["chunk_count"] >= 1
    assert "dry-run 报告" in result.data["report"]
    assert result.data["filename"] == "client-upload.docx"
    assert "docx_path" not in result.data
    assert "provider" not in result.data
    assert "model" not in result.data


@pytest.mark.asyncio
async def test_mcp_stdio_server_review_tool_dry_run_with_base64_docx(tmp_path: Path) -> None:
    docx = _make_minimal_docx(tmp_path)
    transport = StdioTransport(
        command=_python_executable(),
        args=["-m", "src.agents.tender_format_review.mcp_server"],
        cwd=str(_workspace_root()),
    )

    async with Client(transport) as client:
        result = await client.call_tool(
            "review_tender_format",
            {
                "docx_base64": base64.b64encode(docx.read_bytes()).decode("ascii"),
                "docx_filename": "stdio-upload.docx",
                "dry_run": True,
            },
        )

    assert result.data["dry_run"] is True
    assert result.data["chunk_count"] >= 1
    assert result.data["filename"] == "stdio-upload.docx"


def test_create_chat_model_rejects_non_ascii_key(monkeypatch) -> None:
    monkeypatch.setenv("GPU_STACK_API_KEY", "凭证名称：foo")

    try:
        create_chat_model(provider="deepseek")
    except RuntimeError as exc:
        assert "plain ASCII token" in str(exc)
    else:
        raise AssertionError("expected invalid key to fail before HTTP request")


def _make_minimal_docx(tmp_path: Path) -> Path:
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>第一章 招标公告</w:t></w:r></w:p>
    <w:p><w:r><w:t>招标人为测试单位，投标人应按要求递交文件。</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>项目名称</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>工期</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>测试项目</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>30个日历日</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    docx = tmp_path / "sample.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr("word/document.xml", xml)
    return docx


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_executable() -> str:
    import sys

    return sys.executable
