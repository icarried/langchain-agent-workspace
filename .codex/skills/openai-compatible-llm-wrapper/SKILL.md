---
name: openai-compatible-llm-wrapper
description: Wrap an existing agent API or LangChain/LangGraph workflow as an OpenAI-compatible LLM endpoint for Dify, FastGPT, or similar agent platforms. Use when a slow or file-processing agent should be called through an LLM/model node, support /v1/models and /v1/chat/completions, stream SSE chunks, accept prompt-injected file links such as FastGPT array string URLs, or troubleshoot custom OpenAI-compatible provider integration.
---

# OpenAI-compatible LLM Wrapper

Use this skill to expose an agent as a model-like service instead of a normal REST tool. This is most useful when Dify/FastGPT workflow HTTP nodes time out or cannot stream intermediate output, but their LLM/model nodes can call custom OpenAI-compatible providers.

## Choose The Entry

- Keep the original API unchanged when it already works. Add a separate wrapper module or copied agent when production behavior must stay stable.
- Use an OpenAI-compatible wrapper for platform LLM nodes: `GET /v1/models` and `POST /v1/chat/completions`.
- Keep REST `/review` or equivalent for direct API callers and tests.
- Use background jobs only for system integrations that can poll; avoid forcing Dify/FastGPT conversation workflows to poll unless the platform cannot stream custom models.

## Minimal API Contract

Implement:

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
```

Use a stable model id, for example `batch-resume-review-agent`. For `/v1/chat/completions`, accept common OpenAI fields and ignore unknown extras:

```json
{
  "model": "agent-model-id",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true
}
```

For `stream=false`, return standard Chat Completions shape with the final report in `choices[0].message.content`. For `stream=true`, return `text/event-stream` with `chat.completion.chunk` JSON lines and finish with:

```text
data: [DONE]
```

Do not return HTTP 400 for generic provider test prompts. If the message lacks business inputs, return 200 with a short readiness message and the required prompt format. Reserve 400 for malformed protocol payloads that the platform cannot recover from.

## Prompt Input Pattern

Ask users to pass business inputs through the LLM prompt in labeled sections:

```text
岗位要求：
{{job_description}}

简历文件：
{{file_links}}

输出要求：
请输出批量简历审查与排序报告。
```

Support these file link renderings after the file section label:

```text
http://.../candidate-a.pdf
http://.../candidate-b.docx
```

```json
[
  "http://.../candidate-a.pdf?X-Amz-Signature=...",
  "http://.../candidate-b.docx?X-Amz-Signature=..."
]
```

FastGPT commonly exposes file links as `array<string>` and may render them as a JSON array. Parse the section block as JSON first when it starts with `[`, then fall back to extracting URLs or one-path-per-line values. Preserve query strings exactly; MinIO/S3 signatures break if the URL is decoded, truncated, or reserialized incorrectly. Sanitize signed URLs before putting them in reports or logs.

Also accept platform-generated attachment text blocks when users upload files through a model chat UI:

```text
附件：
- candidate-a.pdf: http://.../candidate-a.pdf?X-Amz-Signature=...
- candidate-b.docx: http://.../candidate-b.docx?X-Amz-Signature=...
```

When `messages[].content` is a list of OpenAI-style content parts, extract file URLs from `{"type":"file_url","file_url":{"url":"..."}}`, `{"type":"image_url","image_url":{"url":"..."}}`, and a top-level `{"url":"..."}` part when present. Merge those URLs with prompt-extracted paths and de-duplicate them without rewriting query strings.

For resume-style agents that need both job requirements and uploaded files, keep explicit `岗位要求` / `JD` sections as the preferred protocol. If file inputs are already present but no explicit job section is found, use the text before the first file section label (`简历文件`, `简历路径`, `附件`) or `输出要求` as a fallback job description. Preserve Markdown in that fallback text.

## Implementation Pattern

1. Define Pydantic request models with `extra="allow"` so Dify/FastGPT-specific fields do not fail validation.
2. Flatten `messages[].content` from strings and common list parts such as `{"type":"text","text":"..."}`.
3. Extract labeled sections such as `岗位要求`, `简历文件`, and generic `附件`.
4. Extract `file_url.url` and `image_url.url` from content parts and merge them into the file input list.
5. For resume-style prompts, if file inputs exist but the job section is absent, treat the user text before the file section as the job description.
6. If required business inputs are absent, return a readiness completion.
7. If sections are present, build the original agent request and call the existing service function.
8. For streaming, emit an immediate assistant chunk, progress text, periodic heartbeat text for long tasks, the final report, a stop chunk, and `[DONE]`.
9. Surface business errors as assistant text in streaming mode when the caller is an LLM node; platform model calls often display HTTP errors poorly.

When the platform supports think/reasoning displays, send non-final progress to `delta.reasoning_content` and the final answer/report to `delta.content`. Keep this to execution status and evidence-free process summaries; do not expose hidden chain-of-thought. Provide a request flag such as `thinking=false` to fall back to ordinary `content` progress for platforms that ignore reasoning fields.

Keep the wrapper thin. The original agent should still own parsing files, calling OCR/model providers, ranking, and rendering reports.

## Dify/FastGPT Integration

Configure the platform custom provider as:

```text
Base URL: http://<reachable-host>:<port>/v1
Model: <agent-model-id>
API Key: any placeholder if the wrapper does not enforce auth
Stream: enabled
```

Use the platform's LLM/AI conversation node, not a generic HTTP node, when the goal is to stream text into the chat UI. Put file links and other inputs into the node prompt using labeled sections.

When FastGPT runs in Docker/WSL and the wrapper runs on Windows, `127.0.0.1` inside FastGPT is the container, not Windows. Use a verified reachable URL such as a WSL `socat` relay (`http://172.24.0.1:18006/v1`) or another host address reachable from the container.

## Common Failures

- `connect: connection refused`: the platform cannot reach the wrapper. Check whether the caller is in Docker/WSL; do not use `127.0.0.1` unless the wrapper runs in the same container.
- `/health` works but `/v1/models` is 404: the wrong FastAPI app is running, usually the normal REST API instead of the OpenAI-compatible wrapper app.
- Platform reports `bad response status code 400` during model testing: the wrapper rejected a generic test prompt. Return a readiness completion when business inputs are absent.
- `POST /v1` returns 404: normal. Platforms should call `/v1/models` or `/v1/chat/completions`; Base URL should usually be `/v1`.
- File URL 404 from MinIO: confirm the signed URL host/port maps to the actual MinIO instance. If using a relay, preserve the original signed `Host` when required by the existing loader.

## Validation

Test at three layers:

```powershell
python -m pytest tests\agents\test_<agent>_llm.py -q
ruff check src\agents\<agent>_llm tests\agents\test_<agent>_llm.py
```

Manual curl checks from the same network namespace as the platform:

```bash
curl http://<base>/health
curl http://<base>/v1/models
curl -H "Content-Type: application/json" \
  -d '{"model":"agent-model-id","messages":[{"role":"user","content":"hello"}],"stream":false}' \
  http://<base>/v1/chat/completions
```

Then test a real dry-run prompt with file links rendered exactly as the platform sends them.
