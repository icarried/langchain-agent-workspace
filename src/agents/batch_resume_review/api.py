"""Deprecated REST compatibility adapter backed by batch_resume_review_llm."""

from typing import Any

from fastapi import FastAPI

from src.agents.batch_resume_review_llm.api import (
    BatchResumeReviewRequest,
    BatchResumeReviewResponse,
    review,
)


app = FastAPI(title="Batch Resume Review Compatibility API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "batch-resume-review"}


@app.post("/review", response_model=BatchResumeReviewResponse)
def compatibility_review(request: BatchResumeReviewRequest) -> dict[str, Any]:
    return review(request)


__all__ = ["BatchResumeReviewRequest", "BatchResumeReviewResponse", "app", "review"]
