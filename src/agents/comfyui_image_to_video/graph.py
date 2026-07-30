from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.comfyui_video_generation.client import ComfyUIClient
from src.agents.image_generation.inputs import (
    decode_data_url,
    normalize_extracted_source,
)
from src.agents.openai_compatible import OpenAIChatMessage

from .inputs import ParsedInput, parse_input
from .rewriter import PromptRewriteError, PromptRewriter
from .schemas import (
    ImageToVideoOptions,
    ImageToVideoResult,
    ParsedImageToVideoRequest,
)
from .settings import ImageToVideoSettings
from .workflow import ImageToVideoWorkflowRenderer

TERMINAL_STATUSES = {"completed", "failed"}
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class ImageToVideoState(TypedDict, total=False):
    messages: list[OpenAIChatMessage]
    options: ImageToVideoOptions
    input_image: str | None
    video_id: str
    dry_run: bool
    wait_for_completion: bool
    deadline_at: float
    parsed: ParsedInput
    image_data_url: str
    image_bytes: bytes
    image_mime: str
    uploaded_image: str
    rewritten_prompt: str
    rewrite_fallback: bool
    request: ParsedImageToVideoRequest
    workflow: dict[str, Any]
    prompt_id: str
    status: str
    progress: int
    content_url: str
    error: str
    timed_out: bool
    result: ImageToVideoResult


def build_graph(
    client: ComfyUIClient,
    rewriter: PromptRewriter,
    renderer: ImageToVideoWorkflowRenderer,
    settings: ImageToVideoSettings,
):
    async def parse_input_node(state: ImageToVideoState) -> dict[str, Any]:
        return {
            "parsed": parse_input(
                state["messages"],
                state["options"],
                settings,
                input_image=state.get("input_image"),
            )
        }

    async def prepare_image_node(state: ImageToVideoState) -> dict[str, Any]:
        if state["dry_run"]:
            return {
                "image_data_url": "",
                "image_bytes": b"",
                "image_mime": "image/png",
            }
        image_data_url = normalize_extracted_source(
            state["parsed"].image_source,
            max_bytes=settings.comfyui_i2v_max_input_image_bytes,
        )
        image_mime, image_bytes = decode_data_url(
            image_data_url,
            max_bytes=settings.comfyui_i2v_max_input_image_bytes,
        )
        return {
            "image_data_url": image_data_url,
            "image_bytes": image_bytes,
            "image_mime": image_mime,
        }

    async def rewrite_prompt_node(state: ImageToVideoState) -> dict[str, Any]:
        parsed = state["parsed"]
        if state["dry_run"]:
            return {"rewritten_prompt": parsed.prompt, "rewrite_fallback": False}
        try:
            rewritten = await rewriter.rewrite(
                instruction=parsed.prompt,
                history=parsed.history,
                image_data_url=state["image_data_url"],
                size=parsed.size,
                seconds=parsed.seconds,
                fps=parsed.fps,
            )
        except PromptRewriteError:
            return {"rewritten_prompt": parsed.prompt, "rewrite_fallback": True}
        return {"rewritten_prompt": rewritten, "rewrite_fallback": False}

    async def upload_image_node(state: ImageToVideoState) -> dict[str, Any]:
        if state["dry_run"]:
            return {"uploaded_image": "dry-run-input.png"}
        extension = EXTENSIONS[state["image_mime"]]
        uploaded = await client.upload_image(
            state["image_bytes"],
            filename=f"{state['video_id']}{extension}",
            content_type=state["image_mime"],
        )
        return {"uploaded_image": uploaded}

    async def render_workflow_node(state: ImageToVideoState) -> dict[str, Any]:
        parsed = state["parsed"]
        request = ParsedImageToVideoRequest(
            prompt=parsed.prompt,
            rewritten_prompt=state["rewritten_prompt"],
            negative_prompt=parsed.negative_prompt,
            size=parsed.size,
            seconds=parsed.seconds,
            fps=parsed.fps,
            seed=parsed.seed,
            second_seed=parsed.second_seed,
        )
        return {
            "request": request,
            "workflow": renderer.render(
                request,
                uploaded_image=state["uploaded_image"],
                video_id=state["video_id"],
            ),
            "status": "dry_run" if state["dry_run"] else "queued",
            "progress": 0 if state["dry_run"] else 5,
        }

    async def submit_job_node(state: ImageToVideoState) -> dict[str, Any]:
        prompt_id = await client.submit(state["workflow"])
        return {"prompt_id": prompt_id, "status": "queued", "progress": 5}

    async def monitor_job_node(state: ImageToVideoState) -> dict[str, Any]:
        remaining = state["deadline_at"] - time.monotonic()
        if remaining <= 0:
            return {"timed_out": True}
        await asyncio.sleep(min(settings.comfyui_i2v_poll_interval_seconds, remaining))
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

    async def build_response_node(state: ImageToVideoState) -> dict[str, Any]:
        status = state["status"]
        request = state["request"]
        if status == "dry_run":
            text = (
                "图生视频 Agent dry-run 已完成，未下载图片、未调用LLM、未提交GPU任务。\n\n"
                f"参数：{request.size}、{request.seconds}秒、{request.fps} FPS，"
                f"seed={request.seed}。"
            )
        elif status == "completed":
            text = f"图生视频已生成完成。\n\n任务 ID：`{state['video_id']}`"
        elif status == "failed":
            text = f"图生视频生成失败：{state.get('error', 'ComfyUI未提供错误详情')}"
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
            "result": ImageToVideoResult(
                video_id=state["video_id"],
                status=status,
                progress=state.get("progress", 0),
                text=text,
                prompt_id=state.get("prompt_id"),
                content_url=state.get("content_url"),
                error=state.get("error"),
                rewrite_fallback=state.get("rewrite_fallback", False),
                request=request,
            )
        }

    def route_after_render(state: ImageToVideoState) -> str:
        return "build_response" if state["dry_run"] else "submit_job"

    def route_job(state: ImageToVideoState) -> str:
        if not state["wait_for_completion"]:
            return "build_response"
        if state.get("status") in TERMINAL_STATUSES or state.get("timed_out"):
            return "build_response"
        return "monitor_job"

    graph = StateGraph(ImageToVideoState)
    graph.add_node("parse_input", parse_input_node)
    graph.add_node("prepare_image", prepare_image_node)
    graph.add_node("rewrite_prompt", rewrite_prompt_node)
    graph.add_node("upload_image", upload_image_node)
    graph.add_node("render_workflow", render_workflow_node)
    graph.add_node("submit_job", submit_job_node)
    graph.add_node("monitor_job", monitor_job_node)
    graph.add_node("build_response", build_response_node)
    graph.add_edge(START, "parse_input")
    graph.add_edge("parse_input", "prepare_image")
    graph.add_edge("prepare_image", "rewrite_prompt")
    graph.add_edge("rewrite_prompt", "upload_image")
    graph.add_edge("upload_image", "render_workflow")
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
