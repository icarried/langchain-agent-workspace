from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.openai_compatible import OpenAIChatMessage

from .client import ComfyUIClient
from .inputs import parse_video_request
from .schemas import ParsedVideoRequest, VideoGenerationResult, VideoOptions
from .settings import VideoGenerationSettings
from .workflow import WorkflowRenderer

TERMINAL_STATUSES = {"completed", "failed"}


class VideoAgentState(TypedDict, total=False):
    messages: list[OpenAIChatMessage]
    options: VideoOptions
    video_id: str
    dry_run: bool
    wait_for_completion: bool
    deadline_at: float
    request: ParsedVideoRequest
    workflow: dict[str, Any]
    prompt_id: str
    status: str
    progress: int
    content_url: str
    error: str
    timed_out: bool
    result: VideoGenerationResult


def build_graph(
    client: ComfyUIClient,
    renderer: WorkflowRenderer,
    settings: VideoGenerationSettings,
):
    async def parse_request_node(state: VideoAgentState) -> dict[str, Any]:
        return {
            "request": parse_video_request(
                state["messages"], state["options"], settings
            )
        }

    async def render_workflow_node(state: VideoAgentState) -> dict[str, Any]:
        return {
            "workflow": renderer.render(state["request"], state["video_id"]),
            "status": "dry_run" if state["dry_run"] else "queued",
            "progress": 0 if state["dry_run"] else 5,
        }

    async def submit_job_node(state: VideoAgentState) -> dict[str, Any]:
        prompt_id = await client.submit(state["workflow"])
        return {"prompt_id": prompt_id, "status": "queued", "progress": 5}

    async def monitor_job_node(state: VideoAgentState) -> dict[str, Any]:
        remaining = state["deadline_at"] - time.monotonic()
        if remaining <= 0:
            return {"timed_out": True}
        await asyncio.sleep(
            min(settings.comfyui_video_poll_interval_seconds, remaining)
        )
        inspection = await client.inspect(state["prompt_id"])
        values: dict[str, Any] = {
            "status": inspection.status,
            "progress": inspection.progress,
        }
        if inspection.output_url:
            values["content_url"] = inspection.output_url
        if inspection.error:
            values["error"] = inspection.error
        if (
            inspection.status not in TERMINAL_STATUSES
            and time.monotonic() >= state["deadline_at"]
        ):
            values["timed_out"] = True
        return values

    async def build_response_node(state: VideoAgentState) -> dict[str, Any]:
        status = state["status"]
        request = state["request"]
        if status == "dry_run":
            text = (
                "ComfyUI视频生成 Agent dry-run 已完成，未提交GPU任务。\n\n"
                f"参数：{request.size}、{request.seconds}秒、{request.fps} FPS，"
                f"seed={request.seed}。"
            )
        elif status == "completed":
            text = (
                "视频已生成完成。\n\n"
                f"任务 ID：`{state['video_id']}`"
            )
        elif status == "failed":
            text = f"视频生成失败：{state.get('error', 'ComfyUI未提供错误详情')}"
        else:
            reason = (
                "等待超时，任务仍在ComfyUI中继续执行"
                if state.get("timed_out")
                else "任务已提交"
            )
            text = (
                f"{reason}。当前状态：`{status}`，进度 {state.get('progress', 0)}%。\n\n"
                f"ComfyUI prompt ID：`{state.get('prompt_id', '')}`"
            )
        return {
            "result": VideoGenerationResult(
                video_id=state["video_id"],
                status=status,
                progress=state.get("progress", 0),
                text=text,
                prompt_id=state.get("prompt_id"),
                content_url=state.get("content_url"),
                error=state.get("error"),
                request=request,
            )
        }

    def route_after_render(state: VideoAgentState) -> str:
        return "build_response" if state["dry_run"] else "submit_job"

    def route_job(state: VideoAgentState) -> str:
        if not state["wait_for_completion"]:
            return "build_response"
        if state.get("status") in TERMINAL_STATUSES or state.get("timed_out"):
            return "build_response"
        return "monitor_job"

    graph = StateGraph(VideoAgentState)
    graph.add_node("parse_request", parse_request_node)
    graph.add_node("render_workflow", render_workflow_node)
    graph.add_node("submit_job", submit_job_node)
    graph.add_node("monitor_job", monitor_job_node)
    graph.add_node("build_response", build_response_node)
    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "render_workflow")
    graph.add_conditional_edges(
        "render_workflow",
        route_after_render,
        {"submit_job": "submit_job", "build_response": "build_response"},
    )
    graph.add_conditional_edges(
        "submit_job",
        route_job,
        {"monitor_job": "monitor_job", "build_response": "build_response"},
    )
    graph.add_conditional_edges(
        "monitor_job",
        route_job,
        {"monitor_job": "monitor_job", "build_response": "build_response"},
    )
    graph.add_edge("build_response", END)
    return graph.compile()
