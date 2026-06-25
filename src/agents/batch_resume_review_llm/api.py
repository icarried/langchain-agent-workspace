from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import review_resumes


class BatchResumeReviewRequest(BaseModel):
    resume_paths: list[str] = Field(..., min_length=1, description="待审查简历路径或 HTTP(S) URL 列表")
    job_description_path: str | None = Field(None, description="岗位要求文本路径")
    job_description_text: str | None = Field(None, description="岗位要求文本")
    review_guide_path: str | None = Field(None, description="可选统一审查规则 Markdown 路径")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="不调用模型，只验证解析和工作流")


class BatchResumeReviewResponse(BaseModel):
    report: str
    output_path: str
    resume_paths: list[str]
    provider: str
    model: str
    dry_run: bool
    candidate_count: int
    chunk_count: int
    qualified_count: int
    excluded_count: int
    pending_count: int
    ranking: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    pending: list[dict[str, Any]]
    candidates: list[dict[str, Any]]


app = FastAPI(
    title="Batch Resume Review LLM API",
    version="0.1.0",
    description="批量简历筛选、评分和排序 API（OpenAI-compatible 适配版）。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "batch-resume-review-llm"}


@app.post("/review", response_model=BatchResumeReviewResponse)
def review(request: BatchResumeReviewRequest) -> dict[str, Any]:
    try:
        return review_resumes(
            request.resume_paths,
            job_description_path=request.job_description_path,
            job_description_text=request.job_description_text,
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
