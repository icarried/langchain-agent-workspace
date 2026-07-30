from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from src.model_gateway import gpu_stack_connection

from .settings import DepartmentKnowledgeBaseSettings


QUERY_REWRITE_SYSTEM_PROMPT = """你是企业部门知识库的智能查询分解助手。你的任务是把用户问题转换为少量、明确、具体、可独立用于知识库检索的查询，不负责回答问题。

要求：
1. 保留用户问题中的主体、时间、范围、条件和否定限定，不改变原意。
2. 识别可能需要分别检索的子问题；必要时补充业务同义词、上位概念或正式名称，但不得虚构事实、文档名或用户未表达的结论。
3. 单一明确问题只输出一个查询；复合问题才拆分。
4. 每个查询必须能脱离其他条目独立检索，避免“这个、上述、它”等指代。
5. 最多输出 {max_queries} 个查询，按与原问题的相关性排序。
6. 只输出符合 schema 的 {{"queries": [...]}}，不要解释。"""


class QueryRewriter(Protocol):
    def rewrite(self, question: str, *, department: str) -> list[str]: ...


class QueryRewriteError(RuntimeError):
    """Sanitized query-rewrite failure."""


class DeepSeekQueryRewriter:
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

    def rewrite(self, question: str, *, department: str) -> list[str]:
        payload = {
            "model": self.settings.query_rewrite_model,
            "messages": [
                {
                    "role": "system",
                    "content": QUERY_REWRITE_SYSTEM_PROMPT.format(
                        max_queries=self.settings.max_rewritten_queries
                    ),
                },
                {
                    "role": "user",
                    "content": f"部门：{department}\n用户问题：{question.strip()[:6000]}",
                },
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            with httpx.Client(
                timeout=self.settings.query_rewrite_timeout_seconds,
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
            raise QueryRewriteError("query rewrite timed out") from exc
        except httpx.HTTPError as exc:
            raise QueryRewriteError("query rewrite connection failed") from exc
        if response.status_code >= 400:
            raise QueryRewriteError(
                f"query rewrite failed (HTTP {response.status_code})"
            )
        try:
            content = _message_text(response.json())
            value = json.loads(_strip_code_fence(content))
        except (ValueError, TypeError) as exc:
            raise QueryRewriteError("query rewrite returned invalid JSON") from exc
        queries = value.get("queries") if isinstance(value, dict) else None
        if not isinstance(queries, list):
            raise QueryRewriteError("query rewrite response has no queries array")
        result = _normalize_queries(
            queries,
            limit=self.settings.max_rewritten_queries,
        )
        if not result:
            raise QueryRewriteError("query rewrite returned no usable queries")
        return result


def merge_original_query(
    question: str,
    rewritten: list[str],
    *,
    limit: int,
) -> list[str]:
    return _normalize_queries([question, *rewritten], limit=limit)


def _normalize_queries(values: list[Any], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()[:1000]
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


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
    return content.strip() if isinstance(content, str) else ""


def _strip_code_fence(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned
