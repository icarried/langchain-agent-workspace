from __future__ import annotations

import httpx
import pytest

from src.agents.department_knowledge_base.query_rewrite import (
    DeepSeekQueryRewriter,
    QueryRewriteError,
    merge_original_query,
)
from src.agents.department_knowledge_base.settings import (
    DepartmentKnowledgeBaseSettings,
)


def _settings() -> DepartmentKnowledgeBaseSettings:
    return DepartmentKnowledgeBaseSettings(
        query_rewrite_enabled=True,
        max_rewritten_queries=5,
    )


def test_query_rewriter_parses_structured_queries_and_preserves_original() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"queries":["采购验收程序","采购项目交付验收流程"]}'
                            )
                        }
                    }
                ]
            },
        )

    rewriter = DeepSeekQueryRewriter(
        _settings(),
        base_url="https://gpu.example/v1",
        api_key="test",
        transport=httpx.MockTransport(handler),
    )

    rewritten = rewriter.rewrite("采购完成后如何验收？", department="采购实施部")
    queries = merge_original_query(
        "采购完成后如何验收？",
        rewritten,
        limit=5,
    )

    assert queries == [
        "采购完成后如何验收？",
        "采购验收程序",
        "采购项目交付验收流程",
    ]


def test_query_rewriter_rejects_invalid_json_for_caller_fallback() -> None:
    rewriter = DeepSeekQueryRewriter(
        _settings(),
        base_url="https://gpu.example/v1",
        api_key="test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "not-json"}}]},
            )
        ),
    )

    with pytest.raises(QueryRewriteError, match="invalid JSON"):
        rewriter.rewrite("问题", department="采购实施部")


def test_merge_original_query_deduplicates_and_applies_total_limit() -> None:
    assert merge_original_query(
        "采购制度",
        ["采购制度", " 采购 流程 ", "验收规则", "付款规则"],
        limit=3,
    ) == ["采购制度", "采购 流程", "验收规则"]
