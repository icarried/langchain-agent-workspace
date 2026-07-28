from __future__ import annotations

import re
import secrets
from typing import Any

from src.agents.openai_compatible import OpenAIChatMessage

from .schemas import ParsedVideoRequest, VideoOptions
from .settings import VideoGenerationSettings

SIZE_RE = re.compile(r"(?P<width>\d{2,5})\s*[xX×]\s*(?P<height>\d{2,5})")
SECONDS_RE = re.compile(r"(?P<value>\d+)\s*(?:秒|seconds?|secs?|s)", re.IGNORECASE)
FPS_RE = re.compile(r"(?P<value>\d+)\s*(?:fps|帧(?:每秒)?)", re.IGNORECASE)
SEED_RE = re.compile(
    r"(?:seed|随机种子|种子)\s*[：:=]?\s*(?P<value>\d+)", re.IGNORECASE
)
READINESS_TEXTS = {"", "hello", "hi", "test", "你好", "您好", "你是谁"}


def message_text(message: OpenAIChatMessage) -> str:
    content: Any = message.content
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        value = item.get("text")
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts).strip()


def latest_user_text(messages: list[OpenAIChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            text = message_text(message)
            if text:
                return text
    raise ValueError("请提供视频生成提示词")


def is_readiness_probe(messages: list[OpenAIChatMessage]) -> bool:
    if not messages:
        return True
    try:
        text = latest_user_text(messages).strip().lower()
    except ValueError:
        return True
    return text in READINESS_TEXTS


def parse_video_request(
    messages: list[OpenAIChatMessage],
    options: VideoOptions,
    settings: VideoGenerationSettings,
) -> ParsedVideoRequest:
    prompt = latest_user_text(messages)
    size_match = SIZE_RE.search(prompt)
    seconds_match = SECONDS_RE.search(prompt)
    fps_match = FPS_RE.search(prompt)
    seed_match = SEED_RE.search(prompt)

    size = options.size or (
        f"{size_match.group('width')}x{size_match.group('height')}"
        if size_match
        else settings.comfyui_video_default_size
    )
    seconds = options.seconds or (
        int(seconds_match.group("value"))
        if seconds_match
        else settings.comfyui_video_default_seconds
    )
    fps = options.fps or (
        int(fps_match.group("value"))
        if fps_match
        else settings.comfyui_video_default_fps
    )
    seed = options.seed
    if seed is None:
        seed = (
            int(seed_match.group("value")) if seed_match else secrets.randbelow(2**63)
        )
    second_seed = options.second_seed
    if second_seed is None:
        second_seed = secrets.randbelow(2**63)

    if size not in settings.allowed_sizes:
        raise ValueError(
            f"不支持的视频尺寸：{size}；允许值：{', '.join(settings.allowed_sizes)}"
        )
    if seconds > settings.comfyui_video_max_seconds:
        raise ValueError(f"视频时长不能超过 {settings.comfyui_video_max_seconds} 秒")
    if fps > settings.comfyui_video_max_fps:
        raise ValueError(f"视频帧率不能超过 {settings.comfyui_video_max_fps} FPS")

    return ParsedVideoRequest(
        prompt=prompt,
        negative_prompt=options.negative_prompt,
        size=size,
        seconds=seconds,
        fps=fps,
        seed=seed,
        second_seed=second_seed,
        prompt_enhance=options.prompt_enhance,
    )
