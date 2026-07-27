from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from .client import GPUStackClient
from .graph import build_graph
from .settings import ImageGenerationSettings


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    text: str
    image_url: str
    mode: str
    rewritten_prompt: str
    rewrite_fallback: bool

    def content_parts(self) -> list[dict[str, Any]]:
        return [
            {"type": "text", "text": self.text},
            {"type": "image_url", "image_url": {"url": self.image_url}},
        ]


@dataclass(frozen=True, slots=True)
class ImageGenerationProgress:
    stage: str
    message: str
    heartbeat: str


ProgressCallback = Callable[[ImageGenerationProgress], None]


def generate_image(
    messages: list[Any],
    *,
    dry_run: bool = False,
    client: GPUStackClient | None = None,
    settings: ImageGenerationSettings | None = None,
) -> ImageGenerationResult:
    graph = build_graph(client=client, settings=settings)
    state = graph.invoke({"messages": messages, "dry_run": dry_run})
    return _result_from_state(state)


def generate_image_with_progress(
    messages: list[Any],
    *,
    progress: ProgressCallback,
    dry_run: bool = False,
    client: GPUStackClient | None = None,
    settings: ImageGenerationSettings | None = None,
) -> ImageGenerationResult:
    progress(
        ImageGenerationProgress(
            stage="parse_request",
            message="正在解析对话与图片输入。\n",
            heartbeat="解析对话与图片输入",
        )
    )
    graph = build_graph(client=client, settings=settings)
    state: dict[str, Any] = {"messages": messages, "dry_run": dry_run}
    for update in graph.stream(state, stream_mode="updates"):
        for node, values in update.items():
            if isinstance(values, dict):
                state.update(values)
            event = _progress_for_node(node, state)
            if event is not None:
                progress(event)
    return _result_from_state(state)


def _progress_for_node(
    node: str,
    state: dict[str, Any],
) -> ImageGenerationProgress | None:
    if node == "parse_request":
        return ImageGenerationProgress(
            stage=node,
            message="已读取用户指令，正在判断是否需要使用底图。\n",
            heartbeat="判断图片生成模式",
        )
    if node == "select_mode_and_image":
        editing = state.get("mode") == "edit"
        return ImageGenerationProgress(
            stage=node,
            message=(
                "已选择图片编辑模式，正在结合底图改写编辑指令。\n"
                if editing
                else "未检测到底图，已选择文生图模式，正在改写生图提示词。\n"
            ),
            heartbeat="改写图片编辑指令" if editing else "改写生图提示词",
        )
    if node == "rewrite_prompt":
        rewritten = str(state.get("rewritten_prompt", "")).strip()
        if state.get("rewrite_fallback"):
            message = "提示词改写不可用，已安全降级为用户原始指令，开始生成图片。\n"
        else:
            visible_prompt = rewritten[:800]
            suffix = "…" if len(rewritten) > len(visible_prompt) else ""
            message = f"提示词改写完成：{visible_prompt}{suffix}\n开始生成图片。\n"
        return ImageGenerationProgress(
            stage=node,
            message=message,
            heartbeat=(
                "编辑图片" if state.get("mode") == "edit" else "生成图片"
            ),
        )
    if node == "generate_image":
        return ImageGenerationProgress(
            stage=node,
            message="图片处理完成，正在整理返回结果。\n",
            heartbeat="整理图片结果",
        )
    return None


def _result_from_state(state: dict[str, Any]) -> ImageGenerationResult:
    return ImageGenerationResult(
        text=state["response_text"],
        image_url=state["generated_image"],
        mode=state["mode"],
        rewritten_prompt=state["rewritten_prompt"],
        rewrite_fallback=bool(state.get("rewrite_fallback")),
    )
