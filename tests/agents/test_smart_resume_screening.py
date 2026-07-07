from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from typer.testing import CliRunner

from src.agents.smart_resume_screening.api import app
from src.agents.smart_resume_screening.cli import app as cli_app
from src.agents.smart_resume_screening.criteria import build_criteria
from src.agents.smart_resume_screening.graph import build_graph
from src.agents.smart_resume_screening.mcp_server import mcp
from src.agents.smart_resume_screening.resume_loader import load_candidate
from src.agents.smart_resume_screening.scoring import score_candidate
from src.agents.smart_resume_screening.service import screen_resumes

runner = CliRunner()


def test_criteria_extracts_fastgpt_style_conditions() -> None:
    text = "职位名称：AI工程师\n硬性条件：本科，计算机，Python\n优先条件：FastAPI，上线\n淘汰条件：强制通过"

    criteria = build_criteria(job_description=text)

    assert criteria.position_name == "AI工程师"
    assert "本科" in criteria.hard_conditions
    assert "FastAPI" in criteria.bonus_conditions
    assert "强制通过" in criteria.reject_conditions


def test_score_candidate_marks_missing_hard_condition(tmp_path: Path) -> None:
    resume = tmp_path / "candidate.md"
    resume.write_text("# 姓名：王芳\n本科，新闻传播专业。熟悉内容运营。\n", encoding="utf-8")
    candidate = load_candidate(resume)
    criteria = build_criteria(hard_conditions=["本科", "计算机", "Python"], bonus_conditions=["上线"])

    score = score_candidate(candidate, criteria)

    assert score.status == "not_met"
    assert "计算机" in score.missing_hard_conditions
    assert score.total_score < 60


def test_graph_dry_run_ranks_candidates(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# 姓名：李明\n本科，计算机专业，3年 Python 经验，项目上线。\n", encoding="utf-8")
    b.write_text("# 姓名：王芳\n本科，传媒专业，内容运营。\n", encoding="utf-8")
    output = tmp_path / "report.md"
    graph = build_graph()

    result = graph.invoke(
        {
            "resume_paths": [str(a), str(b)],
            "job_description_text": "硬性条件：本科，计算机，Python\n优先条件：上线",
            "output_path": str(output),
            "dry_run": True,
            "provider": "deepseek",
        }
    )

    assert "智能简历筛选 dry-run 报告" in result["final_report"]
    assert "李明" in result["final_report"]
    assert output.exists()


def test_service_dry_run_with_builtin_examples() -> None:
    root = Path(__file__).resolve().parents[2]
    a = root / "src" / "agents" / "smart_resume_screening" / "examples" / "候选人A_匹配.md"
    b = root / "src" / "agents" / "smart_resume_screening" / "examples" / "候选人B_缺硬性.md"
    jd = root / "src" / "agents" / "smart_resume_screening" / "examples" / "人工智能岗位要求.md"

    result = screen_resumes([a, b], job_description_path=jd, dry_run=True)

    assert result["dry_run"] is True
    assert result["candidate_count"] == 2
    assert result["scores"][0]["display_name"] == "李明"


def test_api_screen_dry_run(tmp_path: Path) -> None:
    resume = tmp_path / "candidate.md"
    resume.write_text("# 姓名：李明\n本科，计算机专业，Python。\n", encoding="utf-8")
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["agent"] == "smart-resume-screening"

    response = client.post(
        "/screen",
        json={
            "resume_paths": [str(resume)],
            "hard_conditions": ["本科", "计算机", "Python"],
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["candidate_count"] == 1
    assert "智能简历筛选 dry-run 报告" in data["report"]


def test_cli_screen_subcommand_accepts_builtin_examples() -> None:
    root = Path(__file__).resolve().parents[2]
    a = root / "src" / "agents" / "smart_resume_screening" / "examples" / "候选人A_匹配.md"
    b = root / "src" / "agents" / "smart_resume_screening" / "examples" / "候选人B_缺硬性.md"
    jd = root / "src" / "agents" / "smart_resume_screening" / "examples" / "人工智能岗位要求.md"

    result = runner.invoke(cli_app, ["screen", str(a), str(b), "--job-description", str(jd), "--dry-run"])

    assert result.exit_code == 0
    assert "智能简历筛选 dry-run 报告" in result.output


@pytest.mark.asyncio
async def test_mcp_screen_tool_accepts_base64_resumes() -> None:
    content = "# 姓名：李明\n本科，计算机专业，Python。\n".encode("utf-8")

    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert any(tool.name == "screen_resumes" for tool in tools)
        result = await client.call_tool(
            "screen_resumes",
            {
                "resumes": [{"filename": "candidate.txt", "content_base64": base64.b64encode(content).decode("ascii")}],
                "hard_conditions": ["本科", "计算机", "Python"],
                "dry_run": True,
            },
        )

    assert result.data["dry_run"] is True
    assert result.data["candidate_count"] == 1
    assert result.data["scores"][0]["status"] == "qualified"
