from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .service import review_contract

app = typer.Typer(help="Contract review agent")
console = Console()


@app.callback()
def main() -> None:
    """Review contracts with six-dimensional legal and business risk checks."""


@app.command()
def review(
    contract_path: Path = typer.Argument(..., help="待审查合同路径，支持 .docx/.pdf/.txt；本地样例可使用 .md"),
    client_role: str = typer.Option("甲方", "--client-role", help="委托方在合同中的角色，例如甲方或乙方"),
    contract_type: str = typer.Option("", "--contract-type", help="合同类型，例如采购合同、服务合同"),
    transaction_background: str = typer.Option("", "--transaction-background", help="交易背景"),
    review_guide: Path | None = typer.Option(None, "--review-guide", help="可选审查规则 Markdown 路径"),
    output: Path | None = typer.Option(None, "--output", "-o", help="可选 Markdown 报告输出路径"),
    provider: str = typer.Option("deepseek", "--provider", help="模型 provider: deepseek 或 dashscope"),
    model: str | None = typer.Option(None, "--model", help="可选模型名覆盖"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只解析、分块和生成 dry-run 报告，不调用模型"),
) -> None:
    result = review_contract(
        contract_path,
        client_role=client_role,
        contract_type=contract_type,
        transaction_background=transaction_background,
        review_guide_path=review_guide,
        output_path=output,
        provider=provider,
        model=model,
        dry_run=dry_run,
    )
    console.print(result["report"])
    if result["output_path"]:
        console.print(f"\n[green]报告已写入:[/green] {result['output_path']}")

