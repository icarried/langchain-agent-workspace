from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .service import screen_resumes

app = typer.Typer(help="Smart resume screening agent")
console = Console()


@app.callback()
def main() -> None:
    """Screen resumes with structured hiring criteria and scorecards."""


@app.command()
def screen(
    resume_paths: list[Path] = typer.Argument(..., help="候选人简历路径，支持 .docx/.pdf/.txt/.md"),
    job_description: Path | None = typer.Option(None, "--job-description", "-j", help="可选岗位 JD 文本路径"),
    job_description_text: str | None = typer.Option(None, "--job-description-text", help="可选岗位 JD 文本"),
    position_name: str = typer.Option("", "--position-name", help="职位名称"),
    department: str = typer.Option("", "--department", help="所属部门"),
    level_range: str = typer.Option("", "--level-range", help="职级范围"),
    hard_condition: list[str] | None = typer.Option(None, "--hard-condition", help="硬性条件，可重复"),
    bonus_condition: list[str] | None = typer.Option(None, "--bonus-condition", help="优先条件，可重复"),
    reject_condition: list[str] | None = typer.Option(None, "--reject-condition", help="淘汰条件，可重复"),
    output: Path | None = typer.Option(None, "--output", "-o", help="可选 Markdown 报告输出路径"),
    provider: str = typer.Option("deepseek", "--provider", help="模型 provider: deepseek 或 dashscope"),
    model: str | None = typer.Option(None, "--model", help="可选模型名覆盖"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只解析、打分并生成 dry-run 报告，不调用模型"),
) -> None:
    result = screen_resumes(
        list(resume_paths),
        job_description_path=job_description,
        job_description_text=job_description_text,
        position_name=position_name,
        department=department,
        level_range=level_range,
        hard_conditions=hard_condition or [],
        bonus_conditions=bonus_condition or [],
        reject_conditions=reject_condition or [],
        output_path=output,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )
    console.print(result["report"])
    if result["output_path"]:
        console.print(f"\n[green]报告已写入:[/green] {result['output_path']}")

