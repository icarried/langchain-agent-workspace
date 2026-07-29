from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .service import format_official_document

app = typer.Typer(help="按公司验证规则格式化 DOCX 公文。")


@app.command("format")
def format_command(
    document: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    target = output
    if target is None and not dry_run:
        target = document.with_name(f"{document.stem}-公文格式化.docx")
    result = format_official_document(
        document,
        output_path=target,
        original_filename=document.name,
        dry_run=dry_run,
    )
    typer.echo(result["report"])
    if result["output_path"]:
        typer.echo(f"输出文件：{result['output_path']}")
