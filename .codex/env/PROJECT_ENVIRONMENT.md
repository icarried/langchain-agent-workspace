# Project Environment

This file describes how this project is developed across Windows, WSL, Docker, and optional remote targets.

## Metadata

- Last updated: 2026-07-28
- Updated by: Codex using `$windows-wsl-dev-environment`
- Project name: Agent Workspace
- Project root as opened now: `E:\My_sorcode\--创建智能体工作空间--`
- Environment owner: Windows PowerShell + conda `langchain`; Docker/FastGPT run in WSL `Ubuntu`
- Notes: OpenAI-compatible production traffic now uses a unified gateway on `8008`; Docker Compose is managed in WSL Ubuntu. Treat Codex sandbox observations as one execution scope, not as whole-machine truth.

## Current Unified Deployment (authoritative)

- Windows root: `E:\My_sorcode\--创建智能体工作空间--`
- Verified WSL root: `/mnt/e/My_sorcode/--创建智能体工作空间--`
- Compose file/project: root `compose.yaml`, project `agent-workspace`
- Platform Base URL: `http://<host>:8008/v1`
- 机器人管理平台服务器 Base URL: `http://10.100.5.23:10085/v1`；容器内网关仍监听
  `8008`，服务器通过 `10085:8008` 发布。
- Only gateway publishes `8008:8008`; eight worker services listen on Compose-internal `8080`.
- Models: `batch-resume-review-agent`, `tender-format-review-agent`, `smart-resume-screening-agent`, `contract-review-agent`, `official-document-review-agent`, `langchain-knowledge-base-agent`, `department-knowledge-base-agent`, `image-generation-agent`.
- Department knowledge-base originals use the project-owned `department-kb-minio` service on
  Compose-internal `9000/9001` and named volume `department_kb_minio_data`; neither MinIO port is
  published to the host. The existing `ai-app-platform` MinIO is only an upload transport source.
- GPU Stack Base URL is `http://10.100.5.33:8003/v1`; credentials are stored only through `GPU_STACK_API_KEY` in `.env.local`.
- On this workstation only, WSL reaches the intranet endpoint through its automatically loaded HTTP proxy at `127.0.0.1:7897`. The local ignored `.env` enables Compose profile `local-proxy`; service `gpu-stack-proxy-relay` exposes that loopback-only proxy only on Docker host-gateway `172.17.0.1:17897`. Server deployments must omit this profile and proxy URL and connect directly.
- Start locally without Docker: `python -m src.agent_gateway dev --port 8008`.
- Build/start in WSL: `DOCKER_BUILDKIT=0 docker compose build gateway` then `docker compose up -d`.
- The current Chinese Windows-mounted path triggers a BuildKit session-header ASCII error; retain `DOCKER_BUILDKIT=0` until moved to a pure ASCII Linux path.
- Knowledge-base volume mounts `/app/data/knowledge_bases`; do not use `docker compose down -v` unless deletion is intended.
- Old independent OpenAI ports 8006–8014 and the old knowledge-base Compose are no longer production entries. `resume-review` REST must use a non-8008 debug port.
- Current `ai-app-platform-backend-1` caller network must reach the published gateway at `http://172.27.0.1:8008/v1`; `127.0.0.1:8008` inside that container is refused. Treat `172.27.0.1` as a checked bridge gateway, not a permanent identifier; prefer a shared Docker network and `http://gateway:8008/v1` for durable service discovery.

## Observation Scope And Sandbox Effects

Facts in this file must name the observer. A failed command from the Codex sandbox means "not visible from this sandbox" unless confirmed from the normal Windows user, WSL, or a container.

| Scope | What it represents | Current evidence | How to use it |
| --- | --- | --- | --- |
| Codex sandbox PowerShell | Restricted Windows user/session used by Codex tools | `docker.exe` not on PATH; `wsl.exe -l -v` reports no distro while WSL processes are running | Use for workspace file edits, Windows localhost probes, and conda commands; do not infer Docker absence from this scope alone. |
| Normal Windows user | The user's interactive Windows session | User states Docker is actually in WSL | Prefer this as the authority for desktop/WSL ownership when it conflicts with sandbox discovery. |
| WSL distro | Linux environment that owns Docker/FastGPT | `Ubuntu` verified running from elevated discovery on 2026-06-30 | Run Docker/FastGPT diagnostics with `wsl.exe -d Ubuntu -- bash -lc '<command>'`. |
| Docker containers | FastGPT, MinIO, Dify, and service containers | FastGPT and MinIO containers verified from WSL `Ubuntu` on 2026-06-30 | Verify service DNS, bridge gateway, and published ports from inside containers. |

## Location And Path Mapping

- Primary project environment: Windows
- Windows path: `E:\My_sorcode\--创建智能体工作空间--`
- WSL distro: `Ubuntu`
- WSL path: `/mnt/e/My_sorcode/--创建智能体工作空间--`
- Remote path: `/opt/agent-workspace` on `robotpl`
- Path conversion command: `wsl.exe -d Ubuntu -- wslpath -a 'E:\My_sorcode\--创建智能体工作空间--'`

| Purpose | Windows path | WSL/Linux path | Container path | Notes |
| --- | --- | --- | --- | --- |
| Project root | `E:\My_sorcode\--创建智能体工作空间--` | `/mnt/e/My_sorcode/--创建智能体工作空间--` | `/app` | Verified during T-036 Compose build and runtime validation. |
| Temporary outputs | `E:\My_sorcode\--创建智能体工作空间--\临时文件` | Unknown | Project-specific | Runtime reports and local logs are intentionally ignored by git. |
| Secrets | `E:\My_sorcode\--创建智能体工作空间--\.env.local` and `secrets\` | Unknown | Project-specific | Store only variable names in docs; do not copy values into environment ledgers. |

## Command Ownership

Record where each command must run. Do not mix shell syntax across rows.

| Task | Run from | Working directory | Command | Verification |
| --- | --- | --- | --- | --- |
| Install/update dependencies | Windows PowerShell | Project root | `conda env update -f environment.yml --prune` | `conda activate langchain`; `python -c "import langchain, langgraph"` |
| Start tender format review API | Windows PowerShell | Project root | `uvicorn src.agents.tender_format_review.api:app --reload --port 8001` | `Invoke-RestMethod http://127.0.0.1:8001/docs` or dry-run `/review` |
| Start tender OpenAI-compatible API | Windows PowerShell | Project root | `uvicorn src.agents.tender_format_review.openai_compatible_api:app --host 0.0.0.0 --port 8007` | `GET http://127.0.0.1:8007/v1/models` |
| Start unified gateway | Windows PowerShell | Project root | `python -m src.agent_gateway dev --port 8008` | `GET http://127.0.0.1:8008/v1/models` |
| Start resume review API | Windows PowerShell | Project root | `uvicorn src.agents.resume_review.api:app --reload --port 18004` | Dry-run `/review` with a local text resume; do not use gateway port 8008 |
| Start batch resume API | Windows PowerShell | Project root | `uvicorn src.agents.batch_resume_review_llm.api:app --reload --port 8006` | Dry-run `/review` with sample resume paths |
| Start batch resume LLM API | Windows PowerShell | Project root | `uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006` | `GET http://127.0.0.1:8006/v1/models`; do not run at the same time as its REST API |
| Start knowledge base worker for debugging | Windows PowerShell | Project root | `uvicorn src.agents.langchain_knowledge_base.openai_compatible_api:app --host 127.0.0.1 --port 18008` | `Invoke-RestMethod http://127.0.0.1:18008/health` |
| Start unified Compose | WSL `Ubuntu` | `/mnt/e/My_sorcode/--创建智能体工作空间--` | `DOCKER_BUILDKIT=0 docker compose build gateway` then `docker compose up -d` | `docker compose ps`; only gateway publishes `8008` |
| Inspect deployed unified Compose | Remote host `robotpl` | `/opt/agent-workspace` | `docker compose ps` | Seven workers healthy; gateway publishes `10085:8008` |
| Run all agent tests | Windows PowerShell | Project root | `python -m pytest tests\agents -q` | Test result output |
| Run focused tests | Windows PowerShell | Project root | `python -m pytest tests\agents\test_<agent>.py -q` | Test result output |
| Run linters | Windows PowerShell | Project root | `ruff check .` | Ruff success |

## Services And Call Direction

| Service | Runs in | Listen address | Called from | Caller URL | Health check | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Tender format review API | Windows | `127.0.0.1:8001` or configured host | Windows tools / local clients | `http://127.0.0.1:8001/review` | Dry-run `/review` | Original REST API. |
| Tender MCP HTTP | Windows | `127.0.0.1:8002/mcp` | MCP clients | `http://127.0.0.1:8002/mcp` | MCP client call | Not a normal REST endpoint. |
| Resume review HTTP MCP | Windows | `127.0.0.1:8003/mcp` | MCP clients | `http://127.0.0.1:8003/mcp` | MCP client call | Optional shared MCP mode. |
| Unified agent gateway | WSL Docker / local supervisor | `0.0.0.0:8008` | FastGPT, Dify, local clients | `http://127.0.0.1:8008/v1/models` | Eight registered models when all workers are healthy | Only production public port. |
| Batch resume MCP HTTP | Windows | `127.0.0.1:8005/mcp` | MCP clients | `http://127.0.0.1:8005/mcp` | MCP client call | Optional shared MCP mode. |
| Batch resume API or LLM API | Windows | `127.0.0.1:8006` | Windows tools or bridged FastGPT/Dify | `http://127.0.0.1:8006/...` or relay URL | `/review` or `/v1/models` depending on entrypoint | Canonical `batch_resume_review_llm` REST API and LLM adapter share port; do not run together. |
| Tender OpenAI-compatible API | Windows | `127.0.0.1:8007` | Dify/FastGPT custom model nodes | `http://127.0.0.1:8007/v1` | `/v1/models` | Supports streaming. |
| Knowledge base worker debug API | Windows or Docker | `127.0.0.1:18008` | Windows tools | `http://127.0.0.1:18008/v1` | `/health` | Production calls use the gateway. |
| Department knowledge-base MinIO | WSL Docker `Ubuntu` | Compose-internal `department-kb-minio:9000`; console `9001` | `department-knowledge-base` worker only | `http://department-kb-minio:9000` | `/minio/health/live` | No host port; eight department buckets; credentials only in `.env.local`. |
| GPU Stack proxy relay | WSL Docker host network, workstation-only `local-proxy` profile | `172.17.0.1:17897` | Agent worker containers | `http://host.docker.internal:17897` as HTTP(S) proxy | Compose health check | Relays to WSL auto-proxy `127.0.0.1:7897`; does not expose a public host port. Do not enable on the server. |

## Docker And Containers

- Docker context for this project: WSL `Ubuntu`, Docker context `default`, endpoint `unix:///var/run/docker.sock`
- Compose file(s): `src\agents\langchain_knowledge_base\docker-compose.yml` if present in the independent subproject
- Compose project name: Default from directory unless overridden
- Networks: WSL Docker networks include `fastgpt_app`, `fastgpt_data`, `fastgpt_aiproxy`, `fastgpt_codesandbox`, `fastgpt_opensandbox`; bridge address `172.24.0.1` exists and was previously used for relays
- Volumes: shared knowledge data uses `knowledge_base_data`; department originals use
  `department_kb_minio_data`. Never delete either volume during routine upgrade or rollback.
- Containers that need host access: FastGPT/Dify/MinIO integrations may need to call Windows-hosted APIs

| Container | Network | Gateway observed inside container | Host access method | Verified on |
| --- | --- | --- | --- | --- |
| FastGPT or Dify container | WSL Docker bridge | `172.24.0.1` was previously used | WSL `socat` relay from bridge port to Windows `127.0.0.1:<api-port>` | Previously documented 2026-06-23 / 2026-06-24; Docker-in-WSL ownership user-confirmed on 2026-06-30 |
| fastgpt-app | WSL Docker `fastgpt_app` | Recheck from container before changing relays | Published `0.0.0.0:3000 -> 3000/tcp` | Verified from WSL `Ubuntu` on 2026-06-30 |
| fastgpt-minio | WSL Docker / FastGPT networks | Recheck from container before changing relays | Published `0.0.0.0:9002 -> 9000/tcp`; console `9003 -> 9001/tcp` | Verified from WSL `Ubuntu` on 2026-06-30 |
| minio | WSL Docker bridge | Separate from FastGPT MinIO | Published `0.0.0.0:9000-9001 -> 9000-9001/tcp` | Verified from WSL `Ubuntu` on 2026-06-30 |
| Knowledge base Compose containers | Unknown | Unknown | Docker-published ports or Compose service DNS | Not verified on 2026-06-30 |

## Temporary Mappings

Use this section for relays, tunnels, port forwards, signed URL transport mappings, and other non-permanent compatibility layers.

| Date | Mapping | Why it exists | Validation command/result | Remove when | Owner |
| --- | --- | --- | --- | --- | --- |
| 2026-07-24 | Docker `host.docker.internal:17897` -> host-network sidecar -> WSL `127.0.0.1:7897` HTTP proxy | GPU Stack intranet route requires the user's automatically managed local proxy; Docker workers cannot use WSL loopback directly | WSL proxied `/v1/models` returned 401 without credentials in 0.18s; authenticated image worker call returned all five expected models | Containers gain a directly usable managed proxy or direct intranet route | Project integration |
| 2026-06-23 | Windows API `127.0.0.1:8006` -> WSL `socat` -> Docker bridge `172.24.0.1:18006` | Let FastGPT container call a Windows-hosted batch resume API | Previously validated in task T-021; recheck bridge address before reuse | FastGPT/Dify can directly reach the API or a stable reverse proxy is introduced | Project integration |
| 2026-06-24 | `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002` while preserving signed Host `10.71.2.94:9000` | FastGPT MinIO signed URL host differed from the actual Windows transport port | Reverified from WSL `Ubuntu` on 2026-06-30: `fastgpt-minio` is `9002->9000`; separate `minio` is `9000->9000` | FastGPT/MinIO external signing address is corrected | Project integration |
| 2026-06-25 | Tender LLM wrapper maps `10.71.2.94:9000` transport to `127.0.0.1:9002` while preserving original Host | Same FastGPT/MinIO signed URL compatibility issue for tender `.docx` files | Covered by tests in prior task; not reverified on 2026-06-30 | FastGPT/MinIO external signing address is corrected and compatibility code is removed | Project integration |

## Observed

Use dated bullets for discoveries that may need another confirmation.

- 2026-06-30: Current project root is a Windows path and should be treated as Windows-primary.
- 2026-06-30: `wsl.exe` exists, but no WSL distro was available from `wsl.exe -l -v` in the current Codex sandbox. This is a sandbox visibility fact, not evidence that the normal user has no WSL distro.
- 2026-06-30: Elevated discovery verified WSL `Ubuntu` is running and owns Docker; `docker context ls` shows active `default` context at `unix:///var/run/docker.sock`.
- 2026-06-30: `docker.exe` was not found on Windows PATH in the current Codex sandbox. Docker diagnostics should target WSL `Ubuntu`, not Windows PATH.
- 2026-06-30: WSL `Ubuntu` `docker ps` verified `fastgpt-minio` maps `9002->9000` and a separate `minio` maps `9000->9000`; this is the concrete cause behind the FastGPT/MinIO signed-host transport mismatch.
- 2026-06-30: Conda is available through `D:\ProgramData\miniforge3\Library\bin\conda.bat`; the project environment is named `langchain`.
- 2026-06-30: `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` were not observed in the current PowerShell environment.
- 2026-07-14: Docker container `ai-app-platform-backend-1` on `ai-app-platform_ai_app_platform` (`172.27.0.6`, bridge gateway `172.27.0.1`) reaches unified gateway health and `/v1/models` through `172.27.0.1:8008`; its same-port `127.0.0.1` is refused and `host.docker.internal` does not resolve. Recheck after the platform Compose network is recreated.
- 2026-07-24: WSL `Ubuntu` reaches GPU Stack through automatically loaded `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY=http://127.0.0.1:7897`; a forced direct (`--noproxy`) connection times out. Authenticated `/v1/models` through the proxy returned `deepseek-v4-flash`, `qwen3.5-122b-a10b`, `qwen3-vl-embedding-8b`, `qwen-image` and `qwen-image-edit`.
- 2026-07-27: Real `image-generation-agent` SSE through the Compose gateway returned its first delta in about 0.016 seconds, then node-level execution progress and 5-second generation heartbeats before the final multimodal image content.
- 2026-07-27: Release `20260727-1243-fcbbba248cd8` was deployed to remote host
  `robotpl` under `/opt/agent-workspace`. The server runs eight production services from the
  immutable `linux/amd64` image tag, publishes only `10085:8008`, and created a new empty
  `agent-workspace_knowledge_base_data` volume. Authenticated gateway model discovery,
  Chat Completions, and container-to-GPU-Stack model discovery all passed.
- 2026-07-28: Root Compose validation with the new department knowledge-base worker and project
  MinIO passed from WSL `Ubuntu`. Rendered Compose publishes only gateway `8008`; MinIO `9000/9001`
  remain internal. Dedicated MinIO credentials are configured only in ignored `.env.local`.
  The MinIO service, department worker and rebuilt gateway are running; the gateway advertises
  eight healthy models. A real object archive and a temporary full ingest path (object archive,
  local snapshot, GPU embedding and Chroma manifest) passed and cleaned their test artifacts.
- 2026-07-28: Authenticated GPU Stack model discovery through the configured WSL proxy returned six
  models and confirmed both `qwen3.5-122b-a10b` and `paddleocr-vl-1.6`. A real contract call classified
  the explicit upload request as `save`; a generated text-page image returned non-empty OCR output.
  Direct Codex sandbox PowerShell access without explicitly selecting the local proxy timed out, so
  this is another observer-scope difference rather than an endpoint outage.
- 2026-07-29: Remote host `robotpl` was upgraded through the local Git bundle and incremental
  server-build workflow to commit `934e9af659d75a0eba3ba95be5ebacb5f25cdcaa`, release
  `git-934e9af659d7`, image `agent-workspace:git-934e9af659d7`. All 11 Compose services run,
  all nine agent models are healthy, only gateway publishes `10085:8008`, and both knowledge-base
  named volumes remain present. Authenticated model discovery, GPU Stack, department MinIO,
  platform-to-gateway connectivity and a gateway dry-run all passed.
- 2026-07-30: Remote host `robotpl` was upgraded to commit
  `804858173ca96e53efebb8f46827b86a5f468e52`, release `git-804858173ca9`, image
  `agent-workspace:git-804858173ca9`. The server build installed `fontconfig`, copied the bundled
  official-document fonts and refreshed the font cache. All 12 Compose services run, all ten agent
  models are healthy, only gateway publishes `10085:8008`, and both knowledge-base named volumes
  remain present. GPU Stack, department MinIO, platform-to-gateway connectivity and gateway
  dry-run validation passed.
- 2026-07-30: Remote host `robotpl` was upgraded through WSL `Ubuntu` and the local
  Git-bundle/server-build workflow to commit
  `6124ed133f39b19fece8ea0aa0934aa03de986ad`, release `git-6124ed133f39`, image
  `agent-workspace:git-6124ed133f39`. All 12 Compose services run, all ten agent
  models are healthy, only gateway publishes `10085:8008`, and both knowledge-base
  named volumes remain present. GPU Stack, department MinIO, platform-to-gateway
  connectivity and gateway dry-run validation passed.
- 2026-07-30: Local `ai-app-platform` app 6 “项目交付部知识库” uses model config 7 with
  `attachment.mode=file_url_content_part` and `knowledge_id=project-delivery`. A real upload
  through Windows `127.0.0.1:10081` preserved the Chinese original filename through platform PG,
  structured Chat Completions input, the department worker, local snapshot, manifest and the
  project-owned MinIO object. The local backend container was recreated with temporary
  `MINIO_PUBLIC_ENDPOINT=http://10.71.2.94:10082`; persist this value in the local ignored
  `.env.production` before a future platform Compose recreation. The server value remains
  `http://10.100.5.23:10082`.

## Migration Check

Recheck these when the project is cloned, moved, shared with another person, or opened from a different system.

- Project root path still matches this file.
- WSL distro name and default shell still exist.
- Windows path and WSL path still point to the same files.
- Docker context and Compose project are correct.
- Docker bridge gateway addresses are current.
- Published ports and health check URLs still work.
- Temporary mappings are still necessary and safe.
- MinIO or other signed URLs use reachable external hosts, or documented transport mappings are still valid.
- Secrets are available through documented environment variable names, without storing values here.

## Do Not Store

- Real API keys, tokens, passwords, cookies, or private certificates.
- One-off command output that does not change how future commands should run.
