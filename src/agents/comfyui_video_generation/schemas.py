from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SEED = 2**63 - 1
SIZE_PATTERN = re.compile(r"^(?P<width>[1-9]\d*)x(?P<height>[1-9]\d*)$")


class VideoOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: str | None = None
    seconds: int | None = Field(default=None, ge=1, le=120)
    fps: int | None = Field(default=None, ge=1, le=240)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    second_seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    prompt_enhance: bool = True

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("×", "x")
        match = SIZE_PATTERN.fullmatch(normalized)
        if match is None:
            raise ValueError("size must use WIDTHxHEIGHT format")
        width = int(match.group("width"))
        height = int(match.group("height"))
        if width % 8 or height % 8:
            raise ValueError("video dimensions must be multiples of 8")
        return f"{width}x{height}"


class ParsedVideoRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    size: str
    seconds: int = Field(ge=1, le=120)
    fps: int = Field(ge=1, le=240)
    seed: int = Field(ge=0, le=MAX_SEED)
    second_seed: int = Field(ge=0, le=MAX_SEED)
    prompt_enhance: bool = True


class VideoGenerationResult(BaseModel):
    video_id: str
    status: Literal["dry_run", "queued", "in_progress", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    text: str
    prompt_id: str | None = None
    content_url: str | None = None
    error: str | None = None
    request: ParsedVideoRequest
