from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import review_resume


class ResumeReviewRequest(BaseModel):
    resume_path: str = Field(..., description="待审查简历路径；相对路径按工作空间根目录解析")
    job_description_path: str | None = Field(None, description="可选岗位 JD 文本路径")
    job_description_text: str | None = Field(None, description="可选岗位 JD 文本内容")
    review_guide_path: str | None = Field(None, description="可选审查事项 Markdown 路径")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider: deepseek 或 dashscope")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="只解析、分块和生成 dry-run 报告，不调用模型")


class ResumeReviewResponse(BaseModel):
    report: str
    output_path: str
    resume_path: str
    provider: str
    model: str
    dry_run: bool
    chunk_count: int
    chunks: list[dict[str, Any]]


app = FastAPI(
    title="Resume Review API",
    version="0.1.0",
    description="人力部门简历审查智能体 API，可供前端或编排工作流节点调用。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "resume-review"}


@app.post("/review", response_model=ResumeReviewResponse)
def review(request: ResumeReviewRequest) -> dict[str, Any]:
    try:
        return review_resume(
            request.resume_path,
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
