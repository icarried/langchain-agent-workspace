from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from scripts.package_agent_standalone import build_bundle
from src.agents.batch_resume_review.reference_loader import (
    DEFAULT_UNIVERSITY_REFERENCE_DIR,
    load_university_references,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = WORKSPACE_ROOT / "src" / "agents" / "batch_resume_review"


def test_agent_has_no_workspace_python_imports() -> None:
    violations = []
    for source_path in AGENT_DIR.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        if "from src." in source or "import src." in source:
            violations.append(source_path.relative_to(AGENT_DIR).as_posix())
    assert violations == []


def test_university_references_are_embedded() -> None:
    content = load_university_references()
    assert DEFAULT_UNIVERSITY_REFERENCE_DIR.is_relative_to(AGENT_DIR)
    assert "985" in content
    assert "211" in content
    assert "双一流" in content
    assert "世界大学" in content


def test_build_bundle_contains_runtime_and_distribution_files(tmp_path: Path) -> None:
    archive_path = build_bundle("batch_resume_review", tmp_path)
    root = "batch-resume-review-agent-0.2.0"

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert f"{root}/pyproject.toml" in names
        assert f"{root}/README.md" in names
        assert f"{root}/mcp-config.example.json" in names
        assert f"{root}/mcp_client_example.py" in names
        assert f"{root}/MANIFEST.sha256.json" in names
        assert f"{root}/src/batch_resume_review/graph.py" in names
        assert any(
            name.startswith(f"{root}/src/batch_resume_review/references/universities/")
            and name.endswith(".md")
            for name in names
        )
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        assert not any(name.endswith(".env.local") for name in names)
        assert not any("/standalone/" in name for name in names)

        checksums = json.loads(archive.read(f"{root}/MANIFEST.sha256.json"))
        assert checksums["algorithm"] == "sha256"
        assert "src/batch_resume_review/graph.py" in checksums["files"]
        pyproject = tomllib.loads(archive.read(f"{root}/pyproject.toml").decode("utf-8"))
        assert pyproject["project"]["name"] == "batch-resume-review-agent"
        assert pyproject["project"]["scripts"]["batch-resume-review"] == (
            "batch_resume_review.cli:app"
        )


def test_extracted_bundle_runs_dry_run_and_mcp_in_process(tmp_path: Path) -> None:
    archive_path = build_bundle("batch_resume_review", tmp_path)
    extract_dir = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)

    bundle_root = extract_dir / "batch-resume-review-agent-0.2.0"
    script = r'''
import asyncio
import base64
from pathlib import Path

from fastmcp import Client
from batch_resume_review.mcp_server import mcp
from batch_resume_review.service import review_resumes

root = Path.cwd()
examples = root / "src" / "batch_resume_review" / "examples"
resumes = sorted(examples.glob("候选示例*.md"))[:2]
jd = examples / "人工智能开发工程师岗位要求.md"
result = review_resumes(resumes, job_description_path=jd, dry_run=True)
assert result["candidate_count"] == 2
assert "批量简历审查" in result["report"]

async def verify_mcp():
    upload_path = resumes[0]
    upload = {
        "filename": "candidate.txt",
        "content_base64": base64.b64encode(upload_path.read_bytes()).decode("ascii"),
    }
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert any(tool.name == "review_resumes" for tool in tools)
        response = await client.call_tool(
            "review_resumes",
            {
                "resumes": [upload],
                "job_description_text": jd.read_text(encoding="utf-8"),
                "dry_run": True,
            },
        )
        assert not response.is_error

asyncio.run(verify_mcp())
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(bundle_root / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=bundle_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
