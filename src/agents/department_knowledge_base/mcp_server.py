from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP

from src.agents.mcp_auth import TOKEN_SCOPES_ENV as GLOBAL_TOKEN_SCOPES_ENV
from src.agents.mcp_auth import request_bearer_token, token_scope

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
        scope = _request_scope("department-kb:list", "kb:list")
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
        scope = _request_scope("department-kb:query", "kb:query")
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
        scope = _request_scope("department-kb:import-status", "kb:import-status")
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


def _request_scope(permission: str, legacy_permission: str) -> McpScope:
    token = request_bearer_token()
    scope = _scope_for_token(token, GLOBAL_TOKEN_SCOPES_ENV)
    if scope is not None and permission in scope.permissions:
        return scope
    scope = _scope_for_token(token, TOKEN_SCOPES_ENV)
    if scope is None or legacy_permission not in scope.permissions:
        raise PermissionError("MCP token is not authorized")
    return scope


def _scope_for_token(token: str, env_name: str = TOKEN_SCOPES_ENV) -> McpScope | None:
    selected = token_scope(token, env_name=env_name)
    if selected is None:
        return None
    knowledge_id = selected.get("knowledge_id")
    permissions = selected.get("permissions", [])
    if knowledge_id is None and env_name == GLOBAL_TOKEN_SCOPES_ENV:
        return None
    if not isinstance(knowledge_id, str) or knowledge_id not in DEPARTMENTS:
        raise RuntimeError(f"{env_name} contains an invalid knowledge_id")
    return McpScope(knowledge_id, frozenset(permissions))
