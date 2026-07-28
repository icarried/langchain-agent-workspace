from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .schemas import ParsedVideoRequest

REQUIRED_NODES = {
    "75": "SaveVideo",
    "267:216": "RandomNoise",
    "267:237": "RandomNoise",
    "267:247": "CLIPTextEncode",
    "267:257": "PrimitiveInt",
    "267:258": "PrimitiveInt",
    "267:260": "PrimitiveInt",
    "267:225": "PrimitiveInt",
    "267:266": "PrimitiveStringMultiline",
    "267:330": "PrimitiveBoolean",
}
VIDEO_ID_PATTERN = re.compile(r"^video_[A-Za-z0-9_-]+$")


class WorkflowTemplateError(RuntimeError):
    pass


class WorkflowRenderer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.template = self._load(path)
        self._validate(self.template)

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkflowTemplateError(f"workflow file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkflowTemplateError("workflow file is not valid JSON") from exc
        if not isinstance(value, dict):
            raise WorkflowTemplateError("workflow root must be an object")
        return value

    @staticmethod
    def _validate(workflow: dict[str, Any]) -> None:
        for node_id, expected_type in REQUIRED_NODES.items():
            node = workflow.get(node_id)
            if not isinstance(node, dict) or node.get("class_type") != expected_type:
                raise WorkflowTemplateError(
                    f"workflow node {node_id} must be {expected_type}"
                )
            if not isinstance(node.get("inputs"), dict):
                raise WorkflowTemplateError(f"workflow node {node_id} has no inputs")

    def render(self, request: ParsedVideoRequest, video_id: str) -> dict[str, Any]:
        if VIDEO_ID_PATTERN.fullmatch(video_id) is None:
            raise ValueError("invalid video id")
        workflow = copy.deepcopy(self.template)
        width, height = (int(value) for value in request.size.split("x", 1))
        workflow["267:266"]["inputs"]["value"] = request.prompt
        if request.negative_prompt is not None:
            workflow["267:247"]["inputs"]["text"] = request.negative_prompt
        workflow["267:257"]["inputs"]["value"] = width
        workflow["267:258"]["inputs"]["value"] = height
        workflow["267:225"]["inputs"]["value"] = request.seconds
        workflow["267:260"]["inputs"]["value"] = request.fps
        workflow["267:237"]["inputs"]["noise_seed"] = request.seed
        workflow["267:216"]["inputs"]["noise_seed"] = request.second_seed
        workflow["267:330"]["inputs"]["value"] = request.prompt_enhance
        workflow["75"]["inputs"]["filename_prefix"] = f"video/agent/{video_id}"
        return workflow
