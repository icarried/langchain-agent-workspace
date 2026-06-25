---
name: langchain-agent-builder
description: Build or update LangChain / LangGraph agents inside this multi-agent workspace. Use when Codex is asked to create a new agent, add an agent workflow, design LangGraph nodes, wire model providers such as DeepSeek or DashScope/Qwen, add prompts/tools/tests/docs, or turn implementation experience into reusable agent-building guidance.
---

# LangChain Agent Builder

Use this skill to create a complete, maintainable LangChain / LangGraph agent in this workspace.

## Workflow

1. Read workspace entry documents first: `README.md`, `AGENTS.md`, `docs/workspace/WORKSPACE_BLUEPRINT.md`, `.agents/tasks/TASK_BOARD.md`.
2. Create or update a dedicated task for the specific agent. Keep agent delivery tasks separate from workspace-construction tasks.
3. Put source under `src/agents/<agent_name>/` and keep the agent name stable, lowercase, and hyphenated in docs.
4. Build small deterministic units before LLM nodes: loaders, parsers, chunkers, schema helpers, provider config.
5. Use LangGraph for multi-step workflows. Prefer explicit nodes such as `load_inputs`, `prepare_context`, `review_chunks`, `aggregate_report`.
6. Add a dry-run path when the workflow handles long files, paid APIs, or fragile external services.
7. Add focused tests for deterministic units and one dry-run graph test.
8. Decide whether the agent needs an OpenAI-compatible LLM wrapper for Dify/FastGPT-style platform LLM nodes.
9. Update `docs/workspace/AGENT_REGISTRY.md`, `docs/development/RUN_AND_DEBUG.md`, and decisions/problem logs when relevant.

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

For platform-facing agents that should be called as a custom LLM, add an optional `openai_compatible_api.py` beside the normal `api.py`. Use the `openai-compatible-llm-wrapper` skill for the detailed contract.

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

## OpenAI-compatible LLM Wrapper Pattern

Use this pattern when a Dify/FastGPT workflow should call the agent through an LLM/model node, stream output to the chat UI, or avoid HTTP-node timeout and polling complexity.

Minimum wrapper behavior:

- Keep the original CLI/API/MCP/service function unchanged.
- Expose `GET /v1/models` and `POST /v1/chat/completions` from a separate FastAPI app.
- Accept `messages`, `model`, `stream`, and ignore unknown OpenAI-compatible fields.
- Return 200 readiness text for generic model-test prompts that do not include business inputs.
- Parse labeled prompt sections such as `岗位要求：` and `简历文件：`.
- Support file links rendered as newline URLs and FastGPT `array<string>` JSON arrays.
- Stream SSE `chat.completion.chunk` events and end with `data: [DONE]`.

Document the platform prompt template, Base URL, model id, port conflict rules, and container/Windows networking path. Validate from inside the same Docker/WSL namespace as the platform, not only from Windows.

## Validation

Run the smallest useful verification:

```powershell
python -m pytest
ruff check .
```

If the agent uses paid or rate-limited models, test `--dry-run` first and document the real invocation separately.
