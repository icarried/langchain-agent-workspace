from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from src.model_gateway import gpu_stack_connection

from .schemas import Intent, IntentDecision
from .settings import DepartmentKnowledgeBaseSettings


INTENT_SYSTEM_PROMPT = """你是企业知识库请求路由器，只输出 JSON。
可选 intent：
- save：用户明确要求保存、归档、上传入库、更新知识库中的附件。
- query：用户询问应当依据当前部门知识库回答的问题。
- list：用户要求查看当前部门已保存的文档或知识库状态。
- help：用户询问使用方式、支持能力或没有提出业务动作。
- unknown：意图不清楚。

安全规则：
1. 附件存在不等于保存；只有用户明确表达保存/入库/归档/更新资料时才选择 save。
2. 不根据用户文字选择或修改部门，部门范围由服务端 knowledge_id 决定。
3. 不执行删除、跨部门访问、权限变更；此类请求选择 unknown。
4. 只返回 {"intent":"...","confidence":0到1}，不要解释。"""


class IntentRecognizer(Protocol):
    def recognize(self, text: str, *, file_count: int) -> IntentDecision: ...


class IntentRecognitionError(RuntimeError):
    """A sanitized intent-model failure."""


class QwenIntentRecognizer:
    def __init__(
        self,
        settings: DepartmentKnowledgeBaseSettings | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or DepartmentKnowledgeBaseSettings()
        if base_url is None or api_key is None:
            connection = gpu_stack_connection()
            base_url = base_url or connection.base_url
            api_key = api_key or connection.api_key
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport

    def recognize(self, text: str, *, file_count: int) -> IntentDecision:
        user_text = text.strip()[:6000]
        payload = {
            "model": self.settings.intent_model,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"附件数量：{file_count}\n"
                        f"用户请求：{user_text or '<空>'}"
                    ),
                },
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 100,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            with httpx.Client(
                timeout=self.settings.intent_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise IntentRecognitionError("Qwen3.5 intent recognition timed out") from exc
        except httpx.HTTPError as exc:
            raise IntentRecognitionError("Qwen3.5 intent recognition connection failed") from exc
        if response.status_code >= 400:
            raise IntentRecognitionError(
                f"Qwen3.5 intent recognition failed (HTTP {response.status_code})"
            )
        try:
            value = response.json()
        except ValueError as exc:
            raise IntentRecognitionError(
                "Qwen3.5 intent recognition returned non-JSON"
            ) from exc
        content = _message_text(value)
        try:
            return IntentDecision.model_validate_json(_strip_code_fence(content))
        except Exception as exc:
            raise IntentRecognitionError(
                "Qwen3.5 intent recognition returned invalid structured output"
            ) from exc


def recognize_intent_dry_run(text: str, *, file_count: int) -> IntentDecision:
    """Conservative deterministic routing for no-network/no-write validation."""
    normalized = text.strip().lower()
    if file_count and any(
        keyword in normalized
        for keyword in ("保存", "入库", "归档", "上传", "更新资料", "store", "save")
    ):
        intent = Intent.SAVE
    elif any(keyword in normalized for keyword in ("文档列表", "查看文档", "知识库状态", "list")):
        intent = Intent.LIST
    elif not normalized or any(keyword in normalized for keyword in ("帮助", "怎么用", "help")):
        intent = Intent.HELP
    else:
        intent = Intent.QUERY
    return IntentDecision(intent=intent, confidence=1)


def _message_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text"))
            for item in content
            if isinstance(item, dict) and item.get("text")
        ).strip()
    return ""


def _strip_code_fence(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned
    return json.dumps(parsed, ensure_ascii=False)
