from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .service import review_tender_format

app = typer.Typer(help="招标文件格式审查智能体")
console = Console()


@app.callback()
def main() -> None:
    """招标文件格式审查智能体命令组。"""


@app.command()
def review(
    docx: Path = typer.Argument(..., help="待审查的招标文件 .docx"),
    review_guide: Optional[Path] = typer.Option(None, help="招标文件审查事项 Markdown"),
    catalog: Optional[Path] = typer.Option(None, help="参考目录 txt"),
    output: Optional[Path] = typer.Option(None, help="输出 Markdown 报告路径"),
    provider: str = typer.Option("deepseek", help="deepseek 或 dashscope"),
    model: Optional[str] = typer.Option(None, help="覆盖默认模型名称"),
    dry_run: bool = typer.Option(False, help="只解析和分块，不调用模型"),
) -> None:
    result = review_tender_format(
        docx,
        review_guide_path=review_guide,
        catalog_path=catalog,
        output_path=output,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )
    report = result["report"]
    if output:
        console.print(f"[green]报告已写入:[/green] {output}")
    else:
        console.print(report)
