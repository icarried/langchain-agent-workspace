---
name: langchain-agent-builder
description: Build or update LangChain/LangGraph agents in this workspace, including gateway-registered OpenAI-compatible workers, reusable namespace-isolated knowledge bases, prompts, providers, tests, Docker Compose deployment, and operational documentation.
---

# LangChain Agent Builder

Use this skill to create a complete, maintainable LangChain / LangGraph agent that fits the workspace's unified deployment model.

## Workflow

1. Read workspace entry documents first: `README.md`, `AGENTS.md`, `docs/workspace/WORKSPACE_BLUEPRINT.md`, `.agents/tasks/TASK_BOARD.md`.
2. Create or update a dedicated task for the specific agent. Keep agent delivery tasks separate from workspace-construction tasks.
3. Put source under `src/agents/<agent_name>/`; use a stable lowercase underscore package name and a stable hyphenated public model ID where needed.
4. Build small deterministic units before LLM nodes: loaders, parsers, chunkers, schema helpers, provider config.
5. Use LangGraph for multi-step workflows. Prefer explicit nodes such as `load_inputs`, `prepare_context`, `review_chunks`, `aggregate_report`.
6. Add a dry-run path when the workflow handles long files, paid APIs, or fragile external services.
7. Add focused tests for deterministic units and one dry-run graph test.
8. Decide whether the agent needs an OpenAI-compatible worker for Dify/FastGPT-style platform LLM nodes. If so, use `$openai-compatible-llm-wrapper` and register it in the unified gateway.
9. Update `docs/workspace/AGENT_REGISTRY.md`, `docs/development/RUN_AND_DEBUG.md`, gateway runbook, environment template, decisions/problem logs when relevant.

## Agent Structure

Recommended files:

```text
src/agents/<agent_name>/
├── __init__.py
├── __main__.py
├── cli.py
├── graph.py
├── llm.py
├── prompts.py
├── schemas.py
└── README.md
```

Add domain-specific modules only when needed, for example `docx_loader.py`, `chunking.py`, or `tools.py`.

For platform-facing agents, add `openai_compatible_api.py` beside the normal `api.py`. Reuse `src/agents/openai_compatible.py`, `src/agents/openai_compatible_inputs.py` and `src/agents/remote_files.py`; use `$openai-compatible-llm-wrapper` for the detailed contract. Do not copy an agent package to obtain port isolation.

## Model Provider Pattern

Use `.env.local` for real keys and `.env.example` for variable names only. For OpenAI-compatible providers:

- DeepSeek: `DEEPSEEK_API_KEY`, base URL `https://api.deepseek.com`.
- DashScope/Qwen: `DASHSCOPE_API_KEY`, base URL `https://dashscope.aliyuncs.com/compatible-mode/v1`.

Keep provider configuration separate from graph logic. Let CLI options override defaults, but fail clearly when a required key is missing.

## Long Context Pattern

For documents, logs, or datasets that may exceed model context:

1. Parse into addressable elements with stable ids.
2. Chunk by semantic boundaries first, length second.
3. Keep chunk size conservative enough for prompts, references, and output.
4. Ask chunk nodes for evidence ids and cross-chapter follow-up flags.
5. Add an aggregate node that merges duplicates and lists unresolved cross-chunk checks.

Read `references/long-document-agents.md` when building agents for 50k+ word documents.

## Prompt Pattern

Use separate prompts for each node. Good review prompts require:

- Role and scope.
- Evidence rules.
- Output format.
- Explicit uncertainty labels.
- A prohibition on inventing unseen content.

Avoid asking one node to both inspect raw content and synthesize the final report when the source is long.

## Unified OpenAI-compatible Worker Pattern

Use this pattern when a Dify/FastGPT workflow should call the agent through an LLM/model node, stream output to the chat UI, or avoid HTTP-node timeout and polling complexity. The public endpoint is the unified gateway, not an individual worker port.

Minimum wrapper behavior:

- Keep the original CLI/API/MCP/service function unchanged and use a thin wrapper.
- Expose `GET /health`, `GET /v1/models` and `POST /v1/chat/completions` from the worker FastAPI app.
- Accept `messages`, `model`, `stream`, and ignore unknown OpenAI-compatible fields.
- Return 200 readiness text for generic model-test prompts that do not include business inputs.
- Parse labeled prompt sections such as `岗位要求：` and `简历文件：`.
- Support file links rendered as newline URLs and FastGPT `array<string>` JSON arrays.
- Support platform `附件：` blocks and OpenAI content parts such as `file_url.url` / `image_url.url`.
- For resume-style agents, if file inputs are present but no explicit `岗位要求` / `JD` section exists, use the text before the file section as a fallback job description.
- Stream SSE `chat.completion.chunk` events and end with `data: [DONE]`.

Then complete deployment registration:

1. Choose an immutable model ID such as `<agent>-agent` and register its module/worker URL in `config/agent_gateway.json`.
2. Add a root `compose.yaml` worker service listening on internal `8080`, with healthcheck, resource limit and `restart: unless-stopped`; do not publish a worker port.
3. The only public OpenAI-compatible endpoint is `http://<host>:8008/v1`; models must be visible through gateway `/v1/models` only when healthy.
4. Use `python -m src.agent_gateway dev --port 8008 --models <model-id>` for local supervised development.
5. Preserve a legacy package name only as a documented compatibility shim when needed; do not duplicate business source, examples or references.

Set `AGENT_GATEWAY_API_KEY` for production Bearer authentication. Unknown models must become `404 model_not_found`; registered unhealthy workers must become `503 model_unavailable` at the gateway.

## Reusable Knowledge Base Pattern

For RAG, reuse `src/knowledge_base/`; do not create another standalone `kb_api`, primary/secondary routing scheme or shared Chroma collection.

```python
manager = KnowledgeBaseManager(namespace="my-agent")
```

- Choose a stable safe-slug namespace unique to the agent and safe-slug knowledge-base names.
- Keep each data set under `data/knowledge_bases/<namespace>/<name>/` with its own `documents/`, `chroma/` and `manifest.json`.
- Use `ingest`, `retrieve`, `answer` and `list_knowledge_bases`; an embedding configuration change requires explicit rebuild.
- Keep management routes worker-internal unless public gateway management is deliberately designed and authorized.

## Shared Remote Attachments

File agents must use the shared parser/remote file modules. Support mounted paths, HTTP(S), `附件：`, content-part `file_url.url` / `image_url.url` and signed S3/MinIO URLs. Configure `AGENT_REMOTE_ALLOWED_HOSTS`, byte/timeout limits and, only for controlled signed-host mismatches, `AGENT_REMOTE_TRANSPORT_OVERRIDES`; do not hardcode environment IP/port rewrites.

Document the platform prompt template, gateway Base URL, model ID, registration, worker service, namespace, attachment policy and container networking path. Validate from inside the same Docker/WSL namespace as the platform, not only from Windows. `127.0.0.1` in a platform container is that container; use a verified reachable gateway address or a shared Docker network DNS name such as `http://gateway:8008/v1`.

## Validation

Run the smallest useful verification:

```powershell
python -m pytest tests -q
ruff check .
```

If the agent uses paid or rate-limited models, test `--dry-run` first and document the real invocation separately. For gateway workers, also run `docker compose config --quiet`, confirm only `8008` is published, and verify stopping one worker removes only its model from the gateway list.
