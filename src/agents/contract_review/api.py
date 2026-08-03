from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import review_contract


class ContractReviewRequest(BaseModel):
    contract_path: str = Field(..., description="待审查合同路径；相对路径按工作空间根目录解析")
    client_role: str = Field("甲方", description="委托方在合同中的角色，例如甲方或乙方")
    contract_type: str = Field("", description="合同类型")
    transaction_background: str = Field("", description="交易背景")
    review_guide_path: str | None = Field(None, description="可选审查规则 Markdown 路径")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider: deepseek")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="只解析、分块和生成 dry-run 报告，不调用模型")


class ContractReviewResponse(BaseModel):
    report: str
    output_path: str
    contract_path: str
    client_role: str
    contract_type: str
    transaction_background: str
    provider: str
    model: str
    dry_run: bool
    chunk_count: int
    chunks: list[dict[str, Any]]


app = FastAPI(
    title="Contract Review API",
    version="0.1.0",
    description="合同六维审查智能体 API，可供前端或编排工作流节点调用。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "contract-review"}


@app.post("/review", response_model=ContractReviewResponse)
def review(request: ContractReviewRequest) -> dict[str, Any]:
    try:
        return review_contract(
            request.contract_path,
            client_role=request.client_role,
            contract_type=request.contract_type,
            transaction_background=request.transaction_background,
            review_guide_path=request.review_guide_path,
            output_path=request.output_path,
            provider=request.provider,
            model=request.model,
            dry_run=request.dry_run,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
