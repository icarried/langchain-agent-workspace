from __future__ import annotations

import asyncio
import time
from contextlib import suppress
import httpx

from .registry import ModelRegistry


class GatewayRuntime:
    def __init__(
        self,
        registry: ModelRegistry,
        *,
        probe_interval: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.registry = registry
        self.probe_interval = probe_interval
        self.client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(connect=5.0, read=None, write=30.0, pool=5.0),
            follow_redirects=False,
        )
        self._probe_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.probe_all()
        self._probe_task = asyncio.create_task(self._probe_loop(), name="agent-gateway-health-probes")

    async def close(self) -> None:
        if self._probe_task:
            self._probe_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._probe_task
        await self.client.aclose()

    async def probe_all(self) -> None:
        await asyncio.gather(
            *(self.probe(model_id) for model_id in self.registry.specs),
            *(self.probe_mcp(server_id) for server_id in self.registry.mcp_specs),
        )

    async def probe(self, model_id: str) -> None:
        spec = self.registry.specs[model_id]
        status = self.registry.statuses[model_id]
        try:
            health = await self.client.get(f"{spec.upstream}/health")
            health.raise_for_status()
            models = await self.client.get(f"{spec.upstream}/v1/models")
            models.raise_for_status()
            ids = {item.get("id") for item in models.json().get("data", [])}
            if model_id not in ids:
                raise ValueError("worker model id does not match registry")
        except Exception as exc:
            status.healthy = False
            status.detail = _safe_error(exc)
        else:
            status.healthy = True
            status.detail = "ok"
        status.checked_at = time.time()

    def mark_unhealthy(self, model_id: str, exc: Exception | str) -> None:
        status = self.registry.statuses[model_id]
        status.healthy = False
        status.detail = _safe_error(exc)
        status.checked_at = time.time()

    async def probe_mcp(self, server_id: str) -> None:
        spec = self.registry.mcp_specs[server_id]
        status = self.registry.mcp_statuses[server_id]
        try:
            response = await self.client.post(
                spec.upstream,
                headers={
                    "accept": "application/json, text/event-stream",
                    "content-type": "application/json",
                    "mcp-protocol-version": "2025-11-25",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": "gateway-health",
                    "method": "tools/list",
                    "params": {},
                },
            )
            response.raise_for_status()
        except Exception as exc:
            status.healthy = False
            status.detail = _safe_error(exc)
        else:
            status.healthy = True
            status.detail = "ok"
        status.checked_at = time.time()

    def mark_mcp_unhealthy(self, server_id: str, exc: Exception | str) -> None:
        status = self.registry.mcp_statuses[server_id]
        status.healthy = False
        status.detail = _safe_error(exc)
        status.checked_at = time.time()

    async def _probe_loop(self) -> None:
        while True:
            await asyncio.sleep(self.probe_interval)
            await self.probe_all()


def _safe_error(error: Exception | str) -> str:
    if isinstance(error, httpx.ConnectError):
        return "connection failed"
    if isinstance(error, httpx.TimeoutException):
        return "health check timed out"
    if isinstance(error, httpx.HTTPStatusError):
        return f"health check returned HTTP {error.response.status_code}"
    if isinstance(error, str):
        return error[:200]
    return f"{type(error).__name__}: {str(error)[:160]}"
