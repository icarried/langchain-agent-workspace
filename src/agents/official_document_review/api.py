from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import review_official_document


class OfficialDocumentReviewRequest(BaseModel):
    document_path: str = Field(..., description="待检查公文路径；相对路径按工作空间根目录解析")
    document_type: str = Field("", description="公文类型，例如通知、请示、报告、函")
    review_guide_path: str | None = Field(None, description="可选审查规则 Markdown 路径")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider: deepseek 或 dashscope")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="只解析、检查并生成 dry-run 报告，不调用模型")


class OfficialDocumentReviewResponse(BaseModel):
    report: str
    output_path: str
    document_path: str
    document_type: str
    provider: str
    model: str
    dry_run: bool
    finding_count: int
    findings: list[dict[str, Any]]


app = FastAPI(
    title="Official Document Review API",
    version="0.1.0",
    description="公文格式检查与优化智能体 API，可供前端或编排工作流节点调用。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "official-document-review"}


@app.post("/review", response_model=OfficialDocumentReviewResponse)
def review(request: OfficialDocumentReviewRequest) -> dict[str, Any]:
    try:
        return review_official_document(
            request.document_path,
            document_type=request.document_type,
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

