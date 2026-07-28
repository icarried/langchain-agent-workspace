# ComfyUI Video Generation Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a workspace-native LangGraph video generation agent that calls ComfyUI directly and is available through the unified OpenAI-compatible gateway without a separate Videos API.

**Architecture:** A dedicated `comfyui_video_generation` worker owns request parsing, safe LTX workflow rendering, ComfyUI submission, polling, and output URL construction. The existing gateway routes Chat Completions by model ID; the worker calls `COMFYUI_VIDEO_BASE_URL` directly.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic Settings, LangGraph, pytest.

---

### Task 1: Configuration, schemas, and request parsing

Create `settings.py`, `schemas.py`, and `inputs.py`. Test Chinese/English parsing, explicit option precedence, and validation bounds.

### Task 2: Safe workflow rendering

Package the LTX 2.3 API workflow under the agent, validate required nodes, and test that only allowlisted inputs change without mutating the template.

### Task 3: Direct ComfyUI client

Implement asynchronous health, submit, history, queue, and output URL behavior. Test with MockTransport, including bounded node-level rejection details.

### Task 4: LangGraph agent and OpenAI-compatible worker

Implement parse, render, submit, monitor, and response nodes; add dry-run, non-streaming, SSE progress, readiness, and sanitized failure behavior.

### Task 5: Gateway, Compose, configuration, and workspace records

Register `comfyui-video-generation-agent`, add an internal-only worker, document environment variables, and update task, decision, registry, and runbook records.

### Task 6: Verification

Run focused and full pytest suites, Ruff, Compose validation, remote ComfyUI read-only checks, and `git diff --check`.
