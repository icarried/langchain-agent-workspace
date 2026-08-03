from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .service import review_resumes

app = typer.Typer(help="Batch resume review and ranking agent")
console = Console()


@app.callback()
def main() -> None:
    """Screen, score, and rank multiple resumes."""


@app.command()
def review(
    resume_paths: list[Path] = typer.Argument(
        ...,
        help="待审查简历路径，可输入多份；支持 .pdf/.doc/.docx/.md/.txt",
    ),
    job_description: Path | None = typer.Option(
        None,
        "--job-description",
        "-j",
        help="岗位要求文本路径；与 --job-description-text 至少提供一个",
    ),
    job_description_text: str | None = typer.Option(
        None,
        "--job-description-text",
        help="岗位要求文本",
    ),
    review_guide: Path | None = typer.Option(
        None,
        "--review-guide",
        help="可选统一审查规则 Markdown 路径",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Markdown 报告输出路径"
    ),
    provider: str = typer.Option(
        "deepseek", "--provider", help="deepseek"
    ),
    model: str | None = typer.Option(None, "--model", help="可选模型名覆盖"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="验证批量解析和工作流，不调用模型"
    ),
) -> None:
    result = review_resumes(
        resume_paths,
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
