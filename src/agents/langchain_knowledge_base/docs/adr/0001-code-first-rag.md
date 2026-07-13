# 0001 - Code-first RAG with demo-only Langflow

Status: implemented for the core API, eval harness, and docs; Langflow demo artifact is minimal and may require manual wiring depending on the installed Langflow version.

## Context

This project needs a maintainable local knowledge base assistant. The main risk is letting the logic drift into a GUI-only flow that is hard to review, test, and refactor.

## Decision

Keep the RAG behavior in Python code:

- FastAPI owns health, ingest, and chat contracts.
- LangChain code owns retrieval and answer generation.
- Chroma stores local vectors through `PersistentClient`.
- Eval questions live in YAML and run through a repeatable harness.
- Langflow is limited to demo/debug HTTP orchestration.

## Consequences

Positive:

- Behavior is diffable in source control.
- Tests and evals can run without a paid model by default.
- The same contract can be used by the API, eval harness, and demo UI.
- The runtime has one fewer moving part because the default deployment does not require a separate Chroma server.

Tradeoffs:

- Langflow does not become the source of truth for prompt or retrieval behavior.
- Demo flow import may vary by Langflow version, so the JSON artifact is intentionally conservative.
- Local and Docker runs persist vectors in different physical places unless `KB_CHROMA_PERSIST_DIR` is set deliberately: local runs default to `data/chroma/`, while Compose mounts the `kb_chroma_data` named volume to `/app/data/chroma`.

## Non-goals

- No multi-agent orchestration.
- No LangGraph workflow.
- No production claim about authorization, tenancy, or automated ingestion.
- No promise that the Langflow artifact imports unchanged on every version.
