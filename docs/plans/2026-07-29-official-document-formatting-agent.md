# Official Document Formatting Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Linux-deployable, deterministic DOCX formatting agent that preserves the validated company formatter and returns the formatted document through an OpenAI-compatible `delta.file` payload.

**Architecture:** The agent accepts exactly one local or remote DOCX, materializes it through the shared attachment transport, invokes the frozen `format_docx(src, dst)` implementation in a LangGraph workflow, and returns the resulting bytes plus execution metadata. The worker exposes the existing unified gateway contract and never connects to AI platform MinIO; `ai-app-platform` will validate and persist the returned DOCX in a later integration task.

**Tech Stack:** Python 3.11, python-docx, LangGraph, FastAPI, OpenAI-compatible Chat Completions/SSE, pytest, Docker Compose.

---

### Task 1: Register the delivery task and freeze formatter assets

**Files:**
- Modify: `.agents/tasks/TASK_BOARD.md`
- Create: `src/agents/official_document_formatting/formatter.py`
- Create: `src/agents/official_document_formatting/fonts/*`

1. Copy the already validated formatter logic without changing its formatting decisions.
2. Package the four provided fonts for the Linux image and record their intended family names.
3. Add tests that format a representative DOCX and assert margins, title/body fonts, line spacing, indentation, table borders, date cleanup, and duplicate-title cleanup.

### Task 2: Build deterministic service and LangGraph workflow

**Files:**
- Create: `src/agents/official_document_formatting/schemas.py`
- Create: `src/agents/official_document_formatting/fonts.py`
- Create: `src/agents/official_document_formatting/graph.py`
- Create: `src/agents/official_document_formatting/service.py`
- Create: `src/agents/official_document_formatting/cli.py`
- Create: `src/agents/official_document_formatting/__main__.py`
- Test: `tests/agents/test_official_document_formatting.py`

1. Validate the input extension, file existence, DOCX package, and maximum size.
2. Report Linux font availability without blocking formatting.
3. Use explicit `validate_input`, `inspect_fonts`, `format_document`, and `build_result` graph nodes.
4. Implement dry-run without writing an output document.
5. Keep the source untouched and choose a deterministic `-公文格式化.docx` output name.

### Task 3: Add OpenAI-compatible file output

**Files:**
- Create: `src/agents/official_document_formatting/openai_compatible_api.py`
- Test: `tests/agents/test_official_document_formatting_llm.py`

1. Parse `公文文件：`, platform `附件：`, JSON arrays, local paths, and `file_url.url` content parts.
2. Materialize remote DOCX inputs through `src/agents/remote_files.py`.
3. Return readiness for generic model probes.
4. Return final file metadata and Base64 in non-streaming `message.file` and streaming `delta.file`.
5. Send progress through `reasoning_content` and terminate SSE with `[DONE]`.

### Task 4: Register and deploy the worker

**Files:**
- Modify: `config/agent_gateway.json`
- Modify: `compose.yaml`
- Modify: `Dockerfile`
- Modify: `.env.example`

1. Register immutable model ID `official-document-formatting-agent`.
2. Add an internal-only worker on port 8080 and gateway health dependency.
3. Install packaged fonts with fontconfig in the Linux image.
4. Keep gateway port 8008 as the only published agent port.

### Task 5: Document and verify

**Files:**
- Create: `src/agents/official_document_formatting/README.md`
- Modify: `docs/workspace/AGENT_REGISTRY.md`
- Modify: `docs/development/RUN_AND_DEBUG.md`
- Modify: `docs/development/AGENT_GATEWAY.md`
- Modify: `docs/workspace/DECISIONS.md`

1. Document the input prompt, output protocol, Linux fonts, size limits, and platform responsibility split.
2. Run focused formatter, worker, gateway, and remote attachment tests.
3. Run the full test suite, Ruff, compile checks, JSON/YAML checks, and `git diff --check`.

