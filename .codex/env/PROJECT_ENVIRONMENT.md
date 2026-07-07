# Project Environment

This file describes how this project is developed across Windows, WSL, Docker, and optional remote targets.

## Metadata

- Last updated: 2026-06-30
- Updated by: Codex using `$windows-wsl-dev-environment`
- Project name: Agent Workspace
- Project root as opened now: `E:\My_sorcode\--创建智能体工作空间--`
- Environment owner: Windows PowerShell + conda `langchain`; Docker/FastGPT run in WSL `Ubuntu`
- Notes: This project currently develops multiple LangChain / LangGraph agents. Treat Codex sandbox observations as one execution scope, not as whole-machine truth. The sandbox user may not see the same WSL distributions, Docker CLI, PATH, or network namespace as the normal interactive user.

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
- WSL path: Unknown until `wslpath -a 'E:\My_sorcode\--创建智能体工作空间--'` is verified from `Ubuntu`
- Remote path: None configured
- Path conversion command: `wsl.exe -d Ubuntu -- wslpath -a 'E:\My_sorcode\--创建智能体工作空间--'`

| Purpose | Windows path | WSL/Linux path | Container path | Notes |
| --- | --- | --- | --- | --- |
| Project root | `E:\My_sorcode\--创建智能体工作空间--` | Unknown until actual WSL distro access is available | Usually project-specific; do not assume | Verify path before running mutating commands through WSL or Docker. |
| Temporary outputs | `E:\My_sorcode\--创建智能体工作空间--\临时文件` | Unknown | Project-specific | Runtime reports and local logs are intentionally ignored by git. |
| Secrets | `E:\My_sorcode\--创建智能体工作空间--\.env.local` and `secrets\` | Unknown | Project-specific | Store only variable names in docs; do not copy values into environment ledgers. |

## Command Ownership

Record where each command must run. Do not mix shell syntax across rows.

| Task | Run from | Working directory | Command | Verification |
| --- | --- | --- | --- | --- |
| Install/update dependencies | Windows PowerShell | Project root | `conda env update -f environment.yml --prune` | `conda activate langchain`; `python -c "import langchain, langgraph"` |
| Start tender format review API | Windows PowerShell | Project root | `uvicorn src.agents.tender_format_review.api:app --reload --port 8001` | `Invoke-RestMethod http://127.0.0.1:8001/docs` or dry-run `/review` |
| Start tender OpenAI-compatible API | Windows PowerShell | Project root | `uvicorn src.agents.tender_format_review.openai_compatible_api:app --host 0.0.0.0 --port 8007` | `GET http://127.0.0.1:8007/v1/models` |
| Start resume review API | Windows PowerShell | Project root | `uvicorn src.agents.resume_review.api:app --reload --port 8004` | Dry-run `/review` with a local text resume |
| Start batch resume API | Windows PowerShell | Project root | `uvicorn src.agents.batch_resume_review.api:app --reload --port 8006` | Dry-run `/review` with sample resume paths |
| Start batch resume LLM API | Windows PowerShell | Project root | `uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006` | `GET http://127.0.0.1:8006/v1/models`; do not run at same time as original batch API |
| Start knowledge base API | Windows PowerShell | `src\agents\langchain_knowledge_base` | `uvicorn kb_api.main:app --host 0.0.0.0 --port 8008` | `Invoke-RestMethod http://127.0.0.1:8008/health` |
| Start Docker Compose for knowledge base | WSL `Ubuntu` | WSL path for `src\agents\langchain_knowledge_base` | `docker compose up --build` | `docker compose ps` from `Ubuntu` |
| Run all agent tests | Windows PowerShell | Project root | `python -m pytest tests\agents -q` | Test result output |
| Run focused tests | Windows PowerShell | Project root | `python -m pytest tests\agents\test_<agent>.py -q` | Test result output |
| Run linters | Windows PowerShell | Project root | `ruff check .` | Ruff success |

## Services And Call Direction

| Service | Runs in | Listen address | Called from | Caller URL | Health check | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Tender format review API | Windows | `127.0.0.1:8001` or configured host | Windows tools / local clients | `http://127.0.0.1:8001/review` | Dry-run `/review` | Original REST API. |
| Tender MCP HTTP | Windows | `127.0.0.1:8002/mcp` | MCP clients | `http://127.0.0.1:8002/mcp` | MCP client call | Not a normal REST endpoint. |
| Resume review HTTP MCP | Windows | `127.0.0.1:8003/mcp` | MCP clients | `http://127.0.0.1:8003/mcp` | MCP client call | Optional shared MCP mode. |
| Resume review API | Windows | `127.0.0.1:8004` | Windows tools / local clients | `http://127.0.0.1:8004/review` | Dry-run `/review` | Original REST API. |
| Batch resume MCP HTTP | Windows | `127.0.0.1:8005/mcp` | MCP clients | `http://127.0.0.1:8005/mcp` | MCP client call | Optional shared MCP mode. |
| Batch resume API or LLM API | Windows | `127.0.0.1:8006` | Windows tools or bridged FastGPT/Dify | `http://127.0.0.1:8006/...` or relay URL | `/review` or `/v1/models` depending on entrypoint | Original API and LLM adapter share port; do not run together. |
| Tender OpenAI-compatible API | Windows | `127.0.0.1:8007` | Dify/FastGPT custom model nodes | `http://127.0.0.1:8007/v1` | `/v1/models` | Supports streaming. |
| Knowledge base API | Windows or Docker | `127.0.0.1:8008` | Windows tools or bridged FastGPT/Dify | `http://127.0.0.1:8008/v1` | `/health` | Run from `src\agents\langchain_knowledge_base`. |

## Docker And Containers

- Docker context for this project: WSL `Ubuntu`, Docker context `default`, endpoint `unix:///var/run/docker.sock`
- Compose file(s): `src\agents\langchain_knowledge_base\docker-compose.yml` if present in the independent subproject
- Compose project name: Default from directory unless overridden
- Networks: WSL Docker networks include `fastgpt_app`, `fastgpt_data`, `fastgpt_aiproxy`, `fastgpt_codesandbox`, `fastgpt_opensandbox`; bridge address `172.24.0.1` exists and was previously used for relays
- Volumes: Knowledge base Compose uses `kb_chroma_data` according to workspace docs
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
