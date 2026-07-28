from __future__ import annotations

import math
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.agents.openai_compatible import OpenAIChatMessage

from .client import ComfyUIClient
from .graph import build_graph
from .schemas import ParsedVideoRequest, VideoGenerationResult, VideoOptions
from .settings import VideoGenerationSettings
from .workflow import WorkflowRenderer


@dataclass(frozen=True, slots=True)
class VideoGenerationProgress:
    stage: str
    message: str


class VideoGenerationService:
    def __init__(
        self,
        settings: VideoGenerationSettings,
        client: ComfyUIClient,
        renderer: WorkflowRenderer | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.renderer = renderer or WorkflowRenderer(
            settings.comfyui_video_workflow_path
        )
        self.graph = build_graph(client, self.renderer, settings)

    async def run(
        self,
        messages: list[OpenAIChatMessage],
        options: VideoOptions,
        *,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> VideoGenerationResult:
        state = await self.graph.ainvoke(
            self._initial_state(
                messages,
                options,
                dry_run=dry_run,
                wait_for_completion=wait_for_completion,
                max_wait_seconds=max_wait_seconds,
            ),
            config={"recursion_limit": self._recursion_limit(max_wait_seconds)},
        )
        return VideoGenerationResult.model_validate(state["result"])

    async def stream(
        self,
        messages: list[OpenAIChatMessage],
        options: VideoOptions,
        *,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> AsyncIterator[VideoGenerationProgress | VideoGenerationResult]:
        state = self._initial_state(
            messages,
            options,
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
                    yield VideoGenerationResult.model_validate(values["result"])

    def _initial_state(
        self,
        messages: list[OpenAIChatMessage],
        options: VideoOptions,
        *,
        dry_run: bool,
        wait_for_completion: bool,
        max_wait_seconds: float | None,
    ) -> dict[str, Any]:
        requested = max_wait_seconds or self.settings.comfyui_video_max_wait_seconds
        wait = min(requested, self.settings.comfyui_video_max_wait_seconds)
        return {
            "messages": messages,
            "options": options,
            "video_id": f"video_{uuid.uuid4().hex}",
            "dry_run": dry_run,
            "wait_for_completion": wait_for_completion,
            "deadline_at": time.monotonic() + wait,
            "status": "queued",
            "progress": 0,
            "timed_out": False,
        }

    def _recursion_limit(self, max_wait_seconds: float | None) -> int:
        wait = min(
            max_wait_seconds or self.settings.comfyui_video_max_wait_seconds,
            self.settings.comfyui_video_max_wait_seconds,
        )
        interval = max(0.01, self.settings.comfyui_video_poll_interval_seconds)
        return max(25, min(10000, math.ceil(wait / interval) + 10))

    @staticmethod
    def _progress(node: str, values: dict[str, Any]) -> VideoGenerationProgress | None:
        if node == "parse_request" and "request" in values:
            request = ParsedVideoRequest.model_validate(values["request"])
            return VideoGenerationProgress(
                node,
                f"已解析视频要求：{request.size}、{request.seconds}秒、{request.fps} FPS。\n",
            )
        if node == "render_workflow":
            return VideoGenerationProgress(node, "已安全渲染LTX 2.3工作流。\n")
        if node == "submit_job":
            return VideoGenerationProgress(node, "视频任务已直接提交到ComfyUI。\n")
        if node == "monitor_job":
            if values.get("timed_out") and "status" not in values:
                return VideoGenerationProgress(
                    node, "等待时间已到，正在返回任务信息。\n"
                )
            return VideoGenerationProgress(
                node,
                f"ComfyUI状态：{values.get('status', 'queued')}，进度 {values.get('progress', 0)}%。\n",
            )
        return None
