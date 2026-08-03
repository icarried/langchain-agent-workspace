from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import review_tender_format


class TenderReviewRequest(BaseModel):
    docx_path: str = Field(..., description="待审查 .docx 路径；相对路径按工作空间根目录解析")
    review_guide_path: str | None = Field(None, description="可选审查事项 Markdown 路径")
    catalog_path: str | None = Field(None, description="可选参考目录 txt 路径")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider: deepseek")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="只解析、分块和生成 dry-run 报告，不调用模型")


class TenderReviewResponse(BaseModel):
    report: str
    output_path: str
    docx_path: str
    provider: str
    model: str
    dry_run: bool
    chunk_count: int
    chunks: list[dict[str, Any]]


app = FastAPI(
    title="Tender Format Review API",
    version="0.1.0",
    description="招标文件格式审查智能体 API，可供前端或编排工作流节点调用。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "tender-format-review"}


@app.post("/review", response_model=TenderReviewResponse)
def review(request: TenderReviewRequest) -> dict[str, Any]:
    try:
        return review_tender_format(
            request.docx_path,
            review_guide_path=request.review_guide_path,
            catalog_path=request.catalog_path,
            output_path=request.output_path,
            provider=request.provider,
            model=request.model,
            dry_run=request.dry_run,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
