from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .service import review_resume

app = typer.Typer(help="Resume review agent")
console = Console()


@app.callback()
def main() -> None:
    """Review resumes for HR screening and job matching."""


@app.command()
def review(
    resume_path: Path = typer.Argument(
        ...,
        help="待审查简历路径，支持 .docx/.pdf/.txt；仓库测试夹具可使用 .md",
    ),
    job_description: Path | None = typer.Option(None, "--job-description", "-j", help="可选岗位 JD 文本路径"),
    job_description_text: str | None = typer.Option(None, "--job-description-text", help="可选岗位 JD 文本"),
    review_guide: Path | None = typer.Option(None, "--review-guide", help="可选审查事项 Markdown 路径"),
    output: Path | None = typer.Option(None, "--output", "-o", help="可选 Markdown 报告输出路径"),
    provider: str = typer.Option("deepseek", "--provider", help="模型 provider: deepseek 或 dashscope"),
    model: str | None = typer.Option(None, "--model", help="可选模型名覆盖"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只解析、分块和生成 dry-run 报告，不调用模型"),
) -> None:
    result = review_resume(
        resume_path,
        job_description_path=job_description,
        job_description_text=job_description_text,
        review_guide_path=review_guide,
        output_path=output,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )
    console.print(result["report"])
    if result["output_path"]:
        console.print(f"\n[green]报告已写入:[/green] {result['output_path']}")
