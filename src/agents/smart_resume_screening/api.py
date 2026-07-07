from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import screen_resumes


class SmartResumeScreeningRequest(BaseModel):
    resume_paths: list[str] = Field(..., description="候选人简历路径列表；相对路径按工作空间根目录解析")
    job_description_path: str | None = Field(None, description="可选岗位 JD 文本路径")
    job_description_text: str | None = Field(None, description="可选岗位 JD 文本")
    position_name: str = Field("", description="职位名称")
    department: str = Field("", description="所属部门")
    level_range: str = Field("", description="职级范围")
    hard_conditions: list[str] = Field(default_factory=list, description="硬性条件")
    bonus_conditions: list[str] = Field(default_factory=list, description="优先条件")
    reject_conditions: list[str] = Field(default_factory=list, description="淘汰条件")
    output_path: str | None = Field(None, description="可选 Markdown 报告输出路径")
    provider: str = Field("deepseek", description="模型 provider: deepseek 或 dashscope")
    model: str | None = Field(None, description="可选模型名覆盖")
    dry_run: bool = Field(False, description="只解析、打分并生成 dry-run 报告，不调用模型")


class SmartResumeScreeningResponse(BaseModel):
    report: str
    output_path: str
    resume_paths: list[str]
    provider: str
    model: str
    dry_run: bool
    candidate_count: int
    scores: list[dict[str, Any]]
    criteria: dict[str, Any]


app = FastAPI(
    title="Smart Resume Screening API",
    version="0.1.0",
    description="结构化智能简历筛选 API，可供前端或编排工作流节点调用。",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "smart-resume-screening"}


@app.post("/screen", response_model=SmartResumeScreeningResponse)
def screen(request: SmartResumeScreeningRequest) -> dict[str, Any]:
    try:
        return screen_resumes(
            request.resume_paths,
            job_description_path=request.job_description_path,
            job_description_text=request.job_description_text,
            position_name=request.position_name,
            department=request.department,
            level_range=request.level_range,
            hard_conditions=request.hard_conditions,
            bonus_conditions=request.bonus_conditions,
            reject_conditions=request.reject_conditions,
            output_path=request.output_path,
            provider=request.provider,
            model=request.model,
            dry_run=request.dry_run,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

