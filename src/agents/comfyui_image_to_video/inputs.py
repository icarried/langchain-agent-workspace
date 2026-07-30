from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Any

from src.agents.image_generation.inputs import parse_conversation

from .schemas import ImageToVideoOptions
from .settings import ImageToVideoSettings

SIZE_RE = re.compile(r"(?P<width>\d{2,5})\s*[xX×*]\s*(?P<height>\d{2,5})")
SECONDS_RE = re.compile(r"(?P<value>\d+)\s*(?:秒|seconds?|secs?|s)", re.IGNORECASE)
FPS_RE = re.compile(r"(?P<value>\d+)\s*(?:fps|帧(?:每秒)?)", re.IGNORECASE)
SEED_RE = re.compile(
    r"(?:seed|随机种子|种子)\s*[：:=]?\s*(?P<value>\d+)", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class ParsedInput:
    prompt: str
    history: str
    image_source: str
    size: str
    seconds: int
    fps: int
    seed: int
    second_seed: int
    negative_prompt: str | None


def parse_input(
    messages: list[Any],
    options: ImageToVideoOptions,
    settings: ImageToVideoSettings,
    *,
    input_image: str | None = None,
) -> ParsedInput:
    conversation = parse_conversation(messages)
    image_source = input_image or conversation.image_source
    if not image_source:
        raise ValueError("请上传一张输入图片")
    prompt = conversation.instruction.strip() or "让画面自然地动起来"

    size_match = SIZE_RE.search(prompt)
    seconds_match = SECONDS_RE.search(prompt)
    fps_match = FPS_RE.search(prompt)
    seed_match = SEED_RE.search(prompt)

    size = options.size or (
        f"{size_match.group('width')}x{size_match.group('height')}"
        if size_match
        else _named_size(prompt, settings.comfyui_i2v_default_size)
    )
    seconds = options.seconds or (
        int(seconds_match.group("value"))
        if seconds_match
        else settings.comfyui_i2v_default_seconds
    )
    fps = options.fps or (
        int(fps_match.group("value"))
        if fps_match
        else settings.comfyui_i2v_default_fps
    )
    seed = options.seed
    if seed is None:
        seed = int(seed_match.group("value")) if seed_match else secrets.randbelow(2**63)
    second_seed = options.second_seed
    if second_seed is None:
        second_seed = secrets.randbelow(2**63)

    if size not in settings.allowed_sizes:
        raise ValueError(
            f"不支持的视频尺寸：{size}；允许值：{', '.join(settings.allowed_sizes)}"
        )
    if seconds > settings.comfyui_i2v_max_seconds:
        raise ValueError(f"视频时长不能超过 {settings.comfyui_i2v_max_seconds} 秒")
    if fps > settings.comfyui_i2v_max_fps:
        raise ValueError(f"视频帧率不能超过 {settings.comfyui_i2v_max_fps} FPS")

    return ParsedInput(
        prompt=prompt,
        history=conversation.history,
        image_source=image_source,
        size=size,
        seconds=seconds,
        fps=fps,
        seed=seed,
        second_seed=second_seed,
        negative_prompt=options.negative_prompt,
    )


def is_readiness_probe(messages: list[Any]) -> bool:
    if not messages:
        return True
    if len(messages) != 1:
        return False
    try:
        conversation = parse_conversation(messages)
    except ValueError:
        return True
    normalized = re.sub(r"[\s,.!?，。！？]+", "", conversation.instruction).lower()
    return not conversation.image_source and normalized in {
        "hi", "hello", "你好", "ping", "test", "测试", "你是谁"
    }


def _named_size(prompt: str, default: str) -> str:
    normalized = prompt.lower()
    if "1080p" in normalized or "全高清" in normalized:
        return "1080x1920" if "竖" in normalized else "1920x1080"
    if "方形" in normalized or "正方形" in normalized or "1:1" in normalized:
        return "1024x1024"
    if "竖屏" in normalized or "9:16" in normalized:
        return "720x1280"
    if "横屏" in normalized or "16:9" in normalized or "720p" in normalized:
        return "1280x720"
    return default
