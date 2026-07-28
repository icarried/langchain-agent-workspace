from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from .settings import VideoGenerationSettings


class ComfyUIRequestError(RuntimeError):
    """Sanitized ComfyUI transport or workflow error."""


@dataclass(frozen=True, slots=True)
class JobInspection:
    status: str
    progress: int
    output_url: str | None = None
    error: str | None = None


class ComfyUIClient:
    def __init__(
        self,
        settings: VideoGenerationSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or VideoGenerationSettings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.comfyui_video_base_url.rstrip("/"),
            timeout=self.settings.comfyui_video_request_timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )
        self.client_id = str(uuid.uuid4())

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            response = await self._client.get("/system_stats")
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    async def submit(self, workflow: dict[str, Any]) -> str:
        try:
            response = await self._client.post(
                "/prompt", json={"prompt": workflow, "client_id": self.client_id}
            )
        except httpx.TimeoutException as exc:
            raise ComfyUIRequestError("ComfyUI请求超时") from exc
        except httpx.HTTPError as exc:
            raise ComfyUIRequestError("无法连接ComfyUI") from exc
        if response.status_code >= 400:
            raise ComfyUIRequestError(_rejection_message(response))
        try:
            payload = response.json()
        except ValueError as exc:
            raise ComfyUIRequestError("ComfyUI返回了非JSON响应") from exc
        prompt_id = payload.get("prompt_id") if isinstance(payload, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIRequestError("ComfyUI没有返回prompt_id")
        return prompt_id

    async def inspect(self, prompt_id: str) -> JobInspection:
        history = await self._get_json(f"/history/{prompt_id}")
        inspection = self._inspection_from_history(history, prompt_id)
        if inspection is not None:
            return inspection
        queue = await self._get_json("/queue")
        if _queue_contains(queue.get("queue_running"), prompt_id):
            return JobInspection("in_progress", 10)
        if _queue_contains(queue.get("queue_pending"), prompt_id):
            return JobInspection("queued", 5)
        return JobInspection("queued", 5)

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            response = await self._client.get(path)
        except httpx.TimeoutException as exc:
            raise ComfyUIRequestError("ComfyUI状态查询超时") from exc
        except httpx.HTTPError as exc:
            raise ComfyUIRequestError("无法连接ComfyUI") from exc
        if response.status_code >= 400:
            raise ComfyUIRequestError(
                f"ComfyUI状态查询失败（HTTP {response.status_code}）"
            )
        try:
            value = response.json()
        except ValueError as exc:
            raise ComfyUIRequestError("ComfyUI状态响应不是JSON") from exc
        if not isinstance(value, dict):
            raise ComfyUIRequestError("ComfyUI状态响应格式无效")
        return value

    def _inspection_from_history(
        self, payload: dict[str, Any], prompt_id: str
    ) -> JobInspection | None:
        entry: Any = payload.get(prompt_id)
        if entry is None and ("outputs" in payload or "status" in payload):
            entry = payload
        if not isinstance(entry, dict):
            return None
        status = entry.get("status")
        if isinstance(status, dict):
            status_text = str(status.get("status_str", "")).lower()
            if status_text in {"error", "failed"} or status.get("completed") is False:
                return JobInspection("failed", 0, error=_history_error_message(entry))
        output = _extract_video_output(entry.get("outputs"))
        if output is not None:
            return JobInspection("completed", 100, output_url=self.output_url(output))
        if isinstance(status, dict) and status.get("completed") is True:
            return JobInspection("failed", 0, error="ComfyUI执行完成但没有视频输出")
        return None

    def output_url(self, output: dict[str, Any]) -> str:
        query = urlencode(
            {
                "filename": str(output["filename"]),
                "subfolder": str(output.get("subfolder", "")),
                "type": str(output.get("type", "output")),
            }
        )
        return f"{self.settings.public_base_url}/view?{query}"


def _rejection_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"ComfyUI拒绝了工作流（HTTP {response.status_code}）"
    details: list[str] = []
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            details.append(error["message"])
        node_errors = payload.get("node_errors")
        if isinstance(node_errors, dict):
            for node_id, node_error in node_errors.items():
                if not isinstance(node_error, dict):
                    continue
                errors = node_error.get("errors")
                if not isinstance(errors, list):
                    continue
                for item in errors:
                    if isinstance(item, dict) and isinstance(item.get("message"), str):
                        details.append(f"节点 {node_id}: {item['message']}")
    if not details:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        details.append(compact[:800])
    return "ComfyUI拒绝了工作流：" + "；".join(details)[:1200]


def _queue_contains(value: Any, prompt_id: str) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if isinstance(item, dict) and item.get("prompt_id") == prompt_id:
            return True
        if isinstance(item, (list, tuple)) and prompt_id in item:
            return True
    return False


def _extract_video_output(outputs: Any) -> dict[str, Any] | None:
    if not isinstance(outputs, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for key in ("videos", "gifs", "images"):
            items = node_output.get(key)
            if isinstance(items, list):
                candidates.extend(item for item in items if isinstance(item, dict))
        if isinstance(node_output.get("filename"), str):
            candidates.append(node_output)
    for item in candidates:
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        suffix = filename.lower().rsplit(".", 1)[-1]
        if suffix in {"mp4", "webm", "mov", "mkv", "gif"}:
            return item
    return None


def _history_error_message(entry: dict[str, Any]) -> str:
    status = entry.get("status")
    messages = status.get("messages", []) if isinstance(status, dict) else []
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, (list, tuple)) or len(message) < 2:
                continue
            if message[0] == "execution_error" and isinstance(message[1], dict):
                detail = message[1].get("exception_message") or message[1].get(
                    "node_type"
                )
                if isinstance(detail, str) and detail:
                    return f"ComfyUI生成失败：{detail[:800]}"
    return "ComfyUI生成视频失败"
