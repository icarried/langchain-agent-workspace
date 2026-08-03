from __future__ import annotations

import json
import os
import secrets
from typing import Any

from fastmcp.server.dependencies import get_http_request


TOKEN_SCOPES_ENV = "AGENT_MCP_TOKENS_JSON"


def authorize_http_mcp(permission: str) -> dict[str, Any] | None:
    """Authorize a remote HTTP MCP call while preserving local stdio usage."""
    try:
        token = request_bearer_token()
    except RuntimeError:
        return None
    scope = token_scope(token)
    permissions = scope.get("permissions", []) if scope else []
    if not scope or permission not in permissions:
        raise PermissionError("MCP token is not authorized")
    return scope


def request_bearer_token() -> str:
    request = get_http_request()
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PermissionError("MCP bearer token is required")
    return token


def token_scope(token: str, *, env_name: str = TOKEN_SCOPES_ENV) -> dict[str, Any] | None:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{env_name} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{env_name} must be a JSON object")
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
        raise RuntimeError(f"{env_name} token entries must be JSON objects")
    permissions = selected.get("permissions", [])
    if not isinstance(permissions, list) or not all(
        isinstance(item, str) for item in permissions
    ):
        raise RuntimeError(f"{env_name} contains invalid permissions")
    return selected
