from __future__ import annotations

import math
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.agents.comfyui_video_generation.client import ComfyUIClient
from src.agents.openai_compatible import OpenAIChatMessage

from .graph import build_graph
from .rewriter import PromptRewriter
from .schemas import ImageToVideoOptions, ImageToVideoResult
from .settings import ImageToVideoSettings
from .workflow import ImageToVideoWorkflowRenderer


@dataclass(frozen=True, slots=True)
class ImageToVideoProgress:
    stage: str
    message: str


class ImageToVideoService:
    def __init__(
        self,
        settings: ImageToVideoSettings,
        client: ComfyUIClient,
        rewriter: PromptRewriter,
        renderer: ImageToVideoWorkflowRenderer | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.rewriter = rewriter
        self.renderer = renderer or ImageToVideoWorkflowRenderer(
            settings.comfyui_i2v_workflow_path
        )
        self.graph = build_graph(client, rewriter, self.renderer, settings)

    async def run(
        self,
        messages: list[OpenAIChatMessage],
        options: ImageToVideoOptions,
        *,
        input_image: str | None,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> ImageToVideoResult:
        state = await self.graph.ainvoke(
            self._initial_state(
                messages,
                options,
                input_image=input_image,
                dry_run=dry_run,
                wait_for_completion=wait_for_completion,
                max_wait_seconds=max_wait_seconds,
            ),
            config={"recursion_limit": self._recursion_limit(max_wait_seconds)},
        )
        return ImageToVideoResult.model_validate(state["result"])

    async def stream(
        self,
        messages: list[OpenAIChatMessage],
        options: ImageToVideoOptions,
        *,
        input_image: str | None,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> AsyncIterator[ImageToVideoProgress | ImageToVideoResult]:
        state = self._initial_state(
            messages,
            options,
            input_image=input_image,
            dry_run=dry_run,
            wait_for_completion=wait_for_completion,
            max_wait_seconds=max_wait_seconds,
        )
        async for update in self.graph.astream(
            state,
            stream_mode="updates",
            config={"recursion_limit": self._recursion_limit(max_wait_seconds)},
        ):
            for node, values in update.items():
                if not isinstance(values, dict):
                    continue
                event = self._progress(node, values)
                if event is not None:
                    yield event
                if node == "build_response" and "result" in values:
                    yield ImageToVideoResult.model_validate(values["result"])

    def _initial_state(
        self,
        messages: list[OpenAIChatMessage],
        options: ImageToVideoOptions,
        *,
        input_image: str | None,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> dict[str, Any]:
        requested = max_wait_seconds or self.settings.comfyui_i2v_max_wait_seconds
        wait = min(requested, self.settings.comfyui_i2v_max_wait_seconds)
        return {
            "messages": messages,
            "options": options,
            "input_image": input_image,
            "video_id": f"video_i2v_{uuid.uuid4().hex}",
            "dry_run": dry_run,
            "wait_for_completion": wait_for_completion,
            "deadline_at": time.monotonic() + wait,
            "status": "queued",
            "progress": 0,
            "timed_out": False,
        }

    def _recursion_limit(self, max_wait_seconds: float | None) -> int:
        wait = min(
            max_wait_seconds or self.settings.comfyui_i2v_max_wait_seconds,
            self.settings.comfyui_i2v_max_wait_seconds,
        )
        interval = max(0.01, self.settings.comfyui_i2v_poll_interval_seconds)
        return max(25, min(10000, math.ceil(wait / interval) + 15))

    @staticmethod
    def _progress(node: str, values: dict[str, Any]) -> ImageToVideoProgress | None:
        messages = {
            "parse_input": "已解析图生视频要求并校验参数。\n",
            "prepare_image": "已读取并校验输入图片。\n",
            "upload_image": "已将输入图片上传到ComfyUI。\n",
            "render_workflow": "已安全渲染LTX 2.3图生视频工作流。\n",
            "submit_job": "图生视频任务已提交到ComfyUI。\n",
        }
        if node == "rewrite_prompt":
            return ImageToVideoProgress(
                node,
                "提示词改写不可用，已使用原始指令。\n"
                if values.get("rewrite_fallback")
                else "已使用视觉LLM改写图生视频提示词。\n",
            )
        if node == "monitor_job":
            if values.get("timed_out") and "status" not in values:
                return ImageToVideoProgress(node, "等待时间已到，正在返回任务信息。\n")
            return ImageToVideoProgress(
                node,
                f"ComfyUI状态：{values.get('status', 'queued')}，"
                f"进度 {values.get('progress', 0)}%。\n",
            )
        message = messages.get(node)
        return ImageToVideoProgress(node, message) if message else None
