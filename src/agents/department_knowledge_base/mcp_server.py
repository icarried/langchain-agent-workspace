from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from .departments import DEPARTMENTS, get_department
from .service import DepartmentKnowledgeBaseAgent


TOKEN_SCOPES_ENV = "DEPARTMENT_KB_MCP_TOKENS_JSON"


@dataclass(frozen=True, slots=True)
class McpScope:
    knowledge_id: str
    permissions: frozenset[str]


def build_mcp_server(agent: DepartmentKnowledgeBaseAgent) -> FastMCP:
    server = FastMCP(
        "Department Knowledge Base",
        instructions=(
            "Read-only access to explicitly authorized department knowledge spaces. "
            "Use department_kb_query for evidence-grounded answers and "
            "department_kb_get_import_status for existing import tasks."
        ),
        mask_error_details=True,
    )

    @server.tool(
        name="department_kb_list_spaces",
        description="List only the department knowledge spaces authorized for this token.",
    )
    def list_spaces() -> dict[str, Any]:
        scope = _request_scope("kb:list")
        item = get_department(scope.knowledge_id)
        return {
            "knowledge_space": {
                "knowledge_id": item.knowledge_id,
                "display_name": item.display_name,
            }
        }

    @server.tool(
        name="department_kb_query",
        description=(
            "Answer a question from one authorized department knowledge space. "
            "This tool is read-only and never saves attachments or changes an index."
        ),
    )
    def query(
        question: str,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        scope = _request_scope("kb:query")
        if not question.strip():
            raise ValueError("question must not be empty")
        if top_k is not None and not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        result = agent.runtime.query(
            get_department(scope.knowledge_id),
            question.strip(),
            top_k=top_k,
            has_attachments=False,
        )
        return {
            "knowledge_id": result.knowledge_id,
            "department": result.department,
            "answer": result.content,
            "sources": [item.model_dump() for item in result.source_documents],
        }

    @server.tool(
        name="department_kb_get_import_status",
        description=(
            "Read the latest import task or a specified 32-character task id from "
            "one authorized department knowledge space."
        ),
    )
    def import_status(
        task_id: str | None = None,
    ) -> dict[str, Any]:
        scope = _request_scope("kb:import-status")
        text = task_id.strip() if task_id else ""
        result = agent.runtime.import_status(get_department(scope.knowledge_id), text)
        return {
            "knowledge_id": result.knowledge_id,
            "department": result.department,
            "task_id": result.task_id,
            "task_status": result.task_status,
            "message": result.content,
        }

    return server


def _request_scope(permission: str) -> McpScope:
    request = get_http_request()
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PermissionError("MCP bearer token is required")
    scope = _scope_for_token(token)
    if scope is None or permission not in scope.permissions:
        raise PermissionError("MCP token is not authorized")
    return scope


def _scope_for_token(token: str) -> McpScope | None:
    raw = os.getenv(TOKEN_SCOPES_ENV, "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} must be a JSON object")
    selected: Any = None
    for configured_token, value in payload.items():
        if isinstance(configured_token, str) and secrets.compare_digest(
            configured_token,
            token,
        ):
            selected = value
            break
    if selected is None:
        return None
    if not isinstance(selected, dict):
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} token entries must be JSON objects")
    knowledge_id = selected.get("knowledge_id")
    permissions = selected.get("permissions", [])
    if not isinstance(knowledge_id, str) or knowledge_id not in DEPARTMENTS:
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} contains an invalid knowledge_id")
    if not isinstance(permissions, list) or not all(
        isinstance(item, str) for item in permissions
    ):
        raise RuntimeError(f"{TOKEN_SCOPES_ENV} contains invalid permissions")
    return McpScope(knowledge_id, frozenset(permissions))
