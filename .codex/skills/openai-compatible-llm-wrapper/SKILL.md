---
name: openai-compatible-llm-wrapper
description: Wrap an existing workspace agent as a worker behind the unified OpenAI-compatible gateway for Dify, FastGPT, or similar platforms. Use when adding or changing chat completions, SSE, model registration, file attachments, gateway health routing, Docker Compose deployment, or container-to-gateway connectivity.
---

# OpenAI-compatible LLM Worker

Expose each platform-facing agent as a worker, not as another public port. The workspace publishes one gateway on `8008`; callers choose the worker with the OpenAI `model` field.

## Worker Contract

- Keep the original CLI/API/MCP service and business layer intact. Add a thin `openai_compatible_api.py`; do not copy an agent package merely for deployment isolation.
- Implement `GET /health`, `GET /v1/models`, and `POST /v1/chat/completions` in the worker.
- Use a stable model ID and validate it in the worker request.
- Reuse `src/agents/openai_compatible.py` for permissive request/message models and `src/agents/openai_compatible_inputs.py` for content parts and labeled prompt parsing.
- For non-streaming, return normal Chat Completions with final output in `choices[0].message.content`. For streaming, send `chat.completion.chunk` SSE events and terminate with `data: [DONE]`.
- Return a 200 readiness answer for generic platform probes lacking business input. Do not expose internal stack traces; streaming business failures should be readable assistant text.
- Put progress only in `delta.reasoning_content` when `thinking=true`; it must be execution status, never hidden reasoning. Send final output in `delta.content`.

The gateway owns aggregation semantics:

- Unknown model: `404 model_not_found`.
- Registered but unhealthy model: `503 model_unavailable`.
- `GET /v1/models`: healthy workers only.
- `GET /health`: gateway and worker status without secrets.

Do not duplicate these rules in a worker.

## Gateway Registration And Deployment

1. Add the stable model ID, module and worker URL to `config/agent_gateway.json`.
2. Add a dedicated root `compose.yaml` service that listens only on internal `8080`, with healthcheck, resource boundary and `restart: unless-stopped`. Never publish a worker port.
3. Confirm the worker's `/v1/models` reports the same model ID as the registration.
4. For local development, run `python -m src.agent_gateway dev --port 8008 --models <model-id>`; the supervisor chooses loopback worker ports and restarts failed workers with bounded backoff.
5. For production, run root Compose. Only gateway publishes `8008:8008`.

Platform configuration:

```text
Base URL: http://<reachable-host>:8008/v1
Model: <registered-model-id>
API Key: AGENT_GATEWAY_API_KEY when enabled; otherwise a platform placeholder
Stream: enabled
```

Enable `AGENT_GATEWAY_API_KEY` in production and use a Bearer token. Never record its value.

## Prompt And File Inputs

Use explicit business labels, for example:

```text
岗位要求：
{{job_description}}

简历文件：
{{file_links}}

输出要求：请输出批量简历审查与排序报告。
```

Accept text strings, OpenAI content parts, FastGPT JSON `array<string>`, multi-line paths/URLs and platform-generated `附件：` blocks. Extract `file_url.url`, `image_url.url` and top-level `url` parts; merge and de-duplicate without rewriting signed query strings. For resume workers, when files exist but no explicit JD label exists, use text before the first file/attachment/output label as the fallback JD.

## Shared Attachment Transport

Use `src/agents/remote_files.py` for remote input. It supports local mounted paths, HTTP(S), signed S3/MinIO URLs, extension limits, host allowlists, size/timeout limits and temporary-file cleanup.

Configure rather than hardcode environment-specific transport:

- `AGENT_REMOTE_ALLOWED_HOSTS`
- `AGENT_REMOTE_MAX_BYTES`
- `AGENT_REMOTE_TIMEOUT_SECONDS`
- `AGENT_REMOTE_TRANSPORT_OVERRIDES`

Use a transport override only for a controlled signed-host mismatch. Preserve the original Host and query signature; never rewrite the URL text or log a complete signed URL.

## Platform Container Networking

`127.0.0.1` inside a platform container is that container, not the gateway. Verify connectivity from the actual caller container before saving a provider configuration.

The current `ai-app-platform` backend reaches the gateway's published port at `http://172.27.0.1:8008/v1`; its bridge gateway can change when the network is recreated. For a durable same-host deployment, attach the platform backend and `agent-workspace_default` to a shared Docker network and use Compose DNS:

```text
http://gateway:8008/v1
```

Do not assume `host.docker.internal` resolves in WSL Docker. Use a bridge-scoped relay only if the gateway actually runs outside Docker and direct routing cannot work.

## Validation

Run focused protocol and gateway tests, then test from the caller container namespace:

```powershell
python -m pytest tests\agents\test_<agent>_llm.py tests\agent_gateway -q
ruff check .
```

```sh
curl --noproxy '*' http://<gateway>:8008/health
curl --noproxy '*' http://<gateway>:8008/v1/models
curl --noproxy '*' -H 'Content-Type: application/json' \
  -d '{"model":"agent-model-id","messages":[{"role":"user","content":"hello"}],"stream":false}' \
  http://<gateway>:8008/v1/chat/completions
```

Also validate a real dry-run prompt with platform-rendered file links. For Compose changes, run `docker compose config --quiet`, confirm only `8008` is published, stop one worker and verify its model disappears while other models remain usable, then verify it returns after restart.
