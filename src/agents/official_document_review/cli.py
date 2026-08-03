from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .service import review_official_document

app = typer.Typer(help="Official document format review agent")
console = Console()


@app.callback()
def main() -> None:
    """Check and optimize official document format reports."""


@app.command()
def review(
    document_path: Path = typer.Argument(..., help="待检查公文路径，支持 .docx/.pdf/.txt；本地样例可使用 .md"),
    document_type: str = typer.Option("", "--document-type", help="公文类型，例如通知、请示、报告、函"),
    review_guide: Path | None = typer.Option(None, "--review-guide", help="可选审查规则 Markdown 路径"),
    output: Path | None = typer.Option(None, "--output", "-o", help="可选 Markdown 报告输出路径"),
    provider: str = typer.Option("deepseek", "--provider", help="模型 provider: deepseek"),
    model: str | None = typer.Option(None, "--model", help="可选模型名覆盖"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只解析、检查并生成 dry-run 报告，不调用模型"),
) -> None:
    result = review_official_document(
        document_path,
        document_type=document_type,
        review_guide_path=review_guide,
        output_path=output,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )
    console.print(result["report"])
    if result["output_path"]:
        console.print(f"\n[green]报告已写入:[/green] {result['output_path']}")
