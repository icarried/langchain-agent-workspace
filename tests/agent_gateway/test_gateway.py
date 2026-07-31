import json

import httpx
from fastapi.testclient import TestClient

from src.agent_gateway.app import create_app
from src.agent_gateway.registry import McpServerSpec, ModelRegistry, ModelSpec
from src.agent_gateway.runtime import GatewayRuntime


MODEL_ID = "test-agent"


def _build_client(handler, *, healthy: bool = True) -> tuple[TestClient, ModelRegistry]:
    registry = ModelRegistry(
        specs={MODEL_ID: ModelSpec(id=MODEL_ID, app="tests.fake:app", upstream="http://worker")}
    )
    registry.statuses[MODEL_ID].healthy = healthy
    registry.statuses[MODEL_ID].detail = "ok" if healthy else "stopped"
    runtime = GatewayRuntime(registry, transport=httpx.MockTransport(handler))
    return TestClient(create_app(registry, runtime=runtime, manage_lifespan=False)), registry


def test_models_only_lists_healthy_workers():
    client, registry = _build_client(lambda request: httpx.Response(200))
    assert client.get("/v1/models").json()["data"][0]["id"] == MODEL_ID
    registry.statuses[MODEL_ID].healthy = False
    assert client.get("/v1/models").json()["data"] == []


def test_unknown_and_unavailable_models_use_openai_errors():
    client, registry = _build_client(lambda request: httpx.Response(200))
    unknown = client.post("/v1/chat/completions", json={"model": "missing", "messages": []})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "model_not_found"

    registry.statuses[MODEL_ID].healthy = False
    unavailable = client.post("/v1/chat/completions", json={"model": MODEL_ID, "messages": []})
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "model_unavailable"


def test_non_stream_request_preserves_unknown_fields():
    received = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            headers={"content-type": "application/json"},
        )

    client, _ = _build_client(handler)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [],
            "stream": False,
            "thinking": False,
            "knowledge_id": "marketing",
            "vendor_extra": 7,
        },
    )
    assert response.status_code == 200
    assert received["vendor_extra"] == 7
    assert received["thinking"] is False
    assert received["knowledge_id"] == "marketing"


def test_stream_response_is_forwarded_byte_for_byte():
    stream = (
        b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
        b'data: [DONE]\n\n'
    )

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield stream[:20]
            yield stream[20:]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=Stream(), headers={"content-type": "text/event-stream"})

    client, _ = _build_client(handler)
    response = client.post(
        "/v1/chat/completions", json={"model": MODEL_ID, "messages": [], "stream": True}
    )
    assert response.status_code == 200
    assert response.content == stream


def test_optional_bearer_auth(monkeypatch):
    monkeypatch.setenv("AGENT_GATEWAY_API_KEY", "secret")
    client, _ = _build_client(lambda request: httpx.Response(200))
    assert client.get("/v1/models").status_code == 401
    assert client.get("/v1/models", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_probe_requires_worker_to_advertise_registered_model():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"object": "list", "data": [{"id": "different-agent"}]})

    _, registry = _build_client(handler, healthy=False)
    runtime = GatewayRuntime(registry, transport=httpx.MockTransport(handler))
    import asyncio

    asyncio.run(runtime.probe(MODEL_ID))
    asyncio.run(runtime.close())
    assert registry.statuses[MODEL_ID].healthy is False
    assert "does not match" in registry.statuses[MODEL_ID].detail


def test_mcp_proxy_forwards_protocol_headers_and_body():
    received = {}

    class McpStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        received["path"] = request.url.path
        received["authorization"] = request.headers.get("authorization")
        received["protocol"] = request.headers.get("mcp-protocol-version")
        received["body"] = request.content
        return httpx.Response(
            200,
            stream=McpStream(),
            headers={
                "content-type": "text/event-stream",
                "mcp-session-id": "session-1",
            },
        )

    registry = ModelRegistry(
        specs={},
        mcp_specs={
            "department-kb": McpServerSpec(
                id="department-kb",
                upstream="http://worker/mcp",
                health_upstream="http://worker",
                default=True,
            )
        },
    )
    registry.mcp_statuses["department-kb"].healthy = True
    runtime = GatewayRuntime(registry, transport=httpx.MockTransport(handler))
    client = TestClient(create_app(registry, runtime=runtime, manage_lifespan=False))
    response = client.post(
        "/mcp",
        content=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
        headers={
            "Authorization": "Bearer scoped-token",
            "MCP-Protocol-Version": "2025-11-25",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.headers["mcp-session-id"] == "session-1"
    assert received == {
        "path": "/mcp/",
        "authorization": "Bearer scoped-token",
        "protocol": "2025-11-25",
        "body": b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
    }


def test_mcp_health_is_independent_from_model_health():
    registry = ModelRegistry(
        specs={MODEL_ID: ModelSpec(id=MODEL_ID, app="tests.fake:app", upstream="http://worker")},
        mcp_specs={
            "department-kb": McpServerSpec(
                id="department-kb",
                upstream="http://worker/mcp",
                health_upstream="http://worker",
                default=True,
            )
        },
    )
    registry.statuses[MODEL_ID].healthy = True
    registry.mcp_statuses["department-kb"].healthy = False
    runtime = GatewayRuntime(registry, transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    client = TestClient(create_app(registry, runtime=runtime, manage_lifespan=False))

    assert client.get("/v1/models").json()["data"][0]["id"] == MODEL_ID
    assert client.post("/mcp", json={}).status_code == 503
    health = client.get("/health").json()
    assert health["models"][MODEL_ID]["healthy"] is True
    assert health["mcp_servers"]["department-kb"]["healthy"] is False


def test_mcp_rejects_unconfigured_browser_origin(monkeypatch):
    monkeypatch.delenv("AGENT_MCP_ALLOWED_ORIGINS", raising=False)
    registry = ModelRegistry(
        specs={},
        mcp_specs={
            "department-kb": McpServerSpec(
                id="department-kb",
                upstream="http://worker/mcp",
                health_upstream="http://worker",
                default=True,
            )
        },
    )
    registry.mcp_statuses["department-kb"].healthy = True
    runtime = GatewayRuntime(
        registry,
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    client = TestClient(create_app(registry, runtime=runtime, manage_lifespan=False))

    assert client.post(
        "/mcp",
        json={},
        headers={"Origin": "https://untrusted.example"},
    ).status_code == 403


def test_mcp_probe_checks_protocol_endpoint():
    received = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["path"] = request.url.path
        received["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=b'event: message\ndata: {"jsonrpc":"2.0","id":"gateway-health","result":{"tools":[]}}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    registry = ModelRegistry(
        specs={},
        mcp_specs={
            "department-kb": McpServerSpec(
                id="department-kb",
                upstream="http://worker/mcp",
                health_upstream="http://worker",
                default=True,
            )
        },
    )
    runtime = GatewayRuntime(registry, transport=httpx.MockTransport(handler))
    import asyncio

    asyncio.run(runtime.probe_mcp("department-kb"))
    asyncio.run(runtime.close())

    assert registry.mcp_statuses["department-kb"].healthy is True
    assert received["path"] == "/mcp/"
    assert received["payload"]["method"] == "tools/list"
