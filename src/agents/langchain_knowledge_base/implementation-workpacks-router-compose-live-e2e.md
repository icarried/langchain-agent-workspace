# Docker Compose 真实模型 Router E2E 测试实现拆分

> Status note (2026-06-30): 本文是后续 live E2E 的历史拆分草案。当前运行架构已改为 Chroma `PersistentClient` 本地持久化，Compose 默认不启动独立 `chroma` 服务；若继续实现 live E2E，应只启动 `kb-api`，并采集 `kb-api` 日志和 `kb_chroma_data` 卷状态。

## Mission

新增一个长期可回归的 `pytest` E2E 测试：通过 Docker Compose 启动 `kb-api`，使用真实 OpenAI 兼容 embedding/chat 模型，并通过 Chroma `PersistentClient` 持久化卷覆盖 `primary` 与 `secondary` 两个知识库的入库、路由问答、引用和拒答边界。

## Success Criteria

- 仓库提交两份短小 fixture 文档，分别位于 `data/docs/primary/` 与 `data/docs/secondary/`。
- 新增 `tests/e2e/test_router_compose_live.py`，默认跳过，只有 `KB_E2E_LIVE=1` 且 `.env` 存在 `KB_OPENAI_API_KEY` 时运行。
- 测试自动执行 `docker compose up --build -d kb-api`，轮询 `GET /health`，结束时执行 `docker compose down`，不删除 volume。
- E2E 覆盖 primary ingest、secondary ingest、router primary、router secondary、unknown question refusal。
- 断言以响应结构和引用来源为主，只对模型答案做宽松关键词断言。
- 增加 `pytest.mark.e2e` marker，并在 README 或测试文档中说明运行命令。

## Scope

- In scope: E2E fixtures、live compose pytest、pytest marker、README 运行说明、测试辅助函数和失败日志采集。
- Out of scope: 修改现有 API 合同、引入 Langflow、改造 router 策略、删除 Chroma volume、提交 `.env`、默认触发真实模型费用。

## Claim Boundaries

- Allowed to say: 该 E2E 在显式启用和本地 `.env` 配置存在时，会使用 Docker Compose 与真实 OpenAI 兼容模型验证双知识库 RAG 路由链路。
- Not allowed to say: 该测试默认在 CI 运行、完全无费用、验证 LLM router、清理所有持久化数据或覆盖生产级隔离。

## Signals

- 文件信号: `data/docs/primary/e2e_product.md`、`data/docs/secondary/e2e_support.md`、`tests/e2e/test_router_compose_live.py`、`pyproject.toml` marker、README 运行说明存在。
- 命令信号: `docker compose config --quiet` exit code 0；启用 live 环境时 E2E pytest exit code 0。
- API 信号: `/health` 200 且 `model.status == "ok"`；`/ingest` 返回正确 collection 和非零文档/分块；`/v1/retrieval` 返回引用；`/v1/chat/completions` 返回答案。
- 故障信号: health 超时或请求失败时输出 `kb-api` tail logs，并检查 `kb_chroma_data` 卷。

## Disturbances

- `.env` 缺失、`KB_OPENAI_API_KEY` 未配置、base URL 或模型名不可用。
- Docker Desktop 未启动、镜像构建或拉取失败、端口 `8008/8001` 被占用。
- OpenAI 兼容 API 网络不稳定、限流、余额不足或 embedding/chat 模型行为变化。
- Chroma volume 保留导致历史数据污染检索结果。
- 当前实现可能已有未提交变更，需要避免 worker 互相覆盖。

## Control Actions

- 默认跳过 live E2E，必须由 `KB_E2E_LIVE=1` 显式启用。
- Preflight 先检查 `.env`、API key、`docker compose config --quiet`，不满足则 skip。
- Runtime 只由一个 worker 或主 agent 启动 Compose，避免并发占用 Docker/端口。
- 失败时采集 bounded logs，不反复重试；仅对 health 轮询做 120 秒内等待。
- 如果 volume 污染导致断言不稳定，先记录风险，后续再设计 `KB_E2E_RESET_VOLUME=1`，本次不默认删除 volume。

## Local Critical Path

1. 主 agent 确认当前接口结构、Compose 服务名、pytest 配置位置和文档风格。
2. 按 disjoint ownership 分派 fixtures、pytest live E2E、marker/docs、独立静态验证。
3. 主 agent 集成 worker 输出，检查测试断言没有依赖固定生成文本。
4. 最小验证先跑 `docker compose config --quiet` 与非 live pytest collection；只有本地 `.env` 和用户接受费用时才跑 live E2E。

## Work Packages

### WP0: Contract Scout

Tier: worker54mini

Ownership:
- Read/write: 无
- Read-only: `kb_api/main.py`, `kb_api/schemas.py`, `kb_api/settings.py`, `kb_api/router.py`, `docker-compose.yml`, `.env.example`, `pyproject.toml`, `README.md`, `tests/`
- Forbidden: 不修改文件，不启动 Docker，不调用真实模型

Task:
盘点当前 API 响应结构、知识库配置、Compose 服务名、pytest marker 配置位置和现有测试风格，输出实现约束。

Interfaces:
- Inputs: 当前仓库文件。
- Dependencies: none。
- Outputs: 约束报告。

Acceptance:
- 明确 `/health`、`/ingest`、`/v1/retrieval`、`/v1/chat/completions` 的字段路径。
- 明确 primary/secondary collection 名和路由关键词来源。
- 明确 pytest marker 应落在 `pyproject.toml` 还是其他配置文件。
- 明确 E2E 文件应使用哪些已有依赖，不引入不必要新依赖。

Escalation:
- 如果配置与用户方案冲突，停止并报告具体冲突，不做推测性修改。

Stop condition:
- 只做一次 read-only inventory。

Output format:
- Summary:
- Evidence:
- Observed vs expected:
- Files changed:
- Verification:
- Risks / uncertainty:
- Ownership deviations:
- Escalation needed:

### WP1: E2E Fixture Documents

Tier: worker54mini

Ownership:
- Read/write: `data/docs/primary/e2e_product.md`, `data/docs/secondary/e2e_support.md`
- Read-only: `data/docs/`
- Forbidden: 不修改已有非 E2E 文档，不删除 Chroma 数据，不改 API/test 配置

Task:
新增两份短小、语义清晰、低 token 成本的 Markdown fixture 文档，分别服务 primary 与 secondary 路由问答。

Interfaces:
- Inputs: 用户给定 fixture 事实。
- Dependencies: WP0 可选。
- Outputs: 两个 Markdown fixture 文件。

Acceptance:
- primary 文档包含事实: `Primary KB stores product architecture notes and uses Chroma for local retrieval.`
- secondary 文档包含事实: `Secondary KB contains support policy: tickets tagged urgent must receive a first response within 2 hours.`
- 每份文档足够短，避免不必要 embedding/chat 成本。
- 文档路径与 `Settings` 中 primary/secondary docs dir 一致。

Escalation:
- 如果现有 `data/docs/primary` 或 `data/docs/secondary` 目录不存在，可创建目录；不要移动已有文件。

Stop condition:
- 只新增这两份 fixture。

Output format:
- Summary:
- Evidence:
- Files changed:
- Verification:
- Risks / uncertainty:
- Ownership deviations:
- Escalation needed:

### WP2: Live Compose Pytest Implementation

Tier: worker53

Ownership:
- Read/write: `tests/e2e/test_router_compose_live.py`
- Read-only: `kb_api/schemas.py`, `kb_api/main.py`, `docker-compose.yml`, `.env.example`, `data/docs/primary/e2e_product.md`, `data/docs/secondary/e2e_support.md`
- Forbidden: 不修改 API 实现，不修改 Compose，不修改 docs，不删除 volumes，不启动 Langflow

Task:
实现 live E2E pytest：preflight skip、Compose up/down、health polling、API 请求 helper、失败日志采集和五个场景断言。

Interfaces:
- Inputs: 用户测试设计、WP1 fixtures。
- Dependencies: WP1 fixture 文件。
- Outputs: `tests/e2e/test_router_compose_live.py`。

Acceptance:
- 文件使用 `@pytest.mark.e2e`。
- 未设置 `KB_E2E_LIVE=1` 时 skip，不失败。
- `.env` 缺失或不含 `KB_OPENAI_API_KEY` 时 skip，不失败。
- `docker compose config --quiet` 必须成功，否则 fail 或 skip 需给出清晰原因；推荐在 live enabled 后 fail。
- `docker compose up --build -d kb-api` 后最多 120 秒轮询 `http://localhost:8008/health`，每 2 秒一次。
- health 要求 HTTP 200 且 JSON `model.status == "ok"`。
- finally 执行 `docker compose down`，不带 `-v`。
- health 超时或 compose/API 失败时采集:
  - `docker compose logs kb-api --tail 120`
  - `docker volume inspect langchain_knowledge_base_kb_chroma_data`
- primary ingest 断言 `documents_loaded >= 1`、`chunks_written >= 1`、`collection == "knowledge_base_primary"`。
- secondary ingest 断言 `documents_loaded >= 1`、`chunks_written >= 1`、`collection == "knowledge_base_secondary"`。
- primary route 断言 `route.selected_knowledge_base == "primary"`、`refused is False`、至少 1 条 citation、citation source 包含 `primary` 或 `e2e_product.md`。
- secondary route 断言 `route.selected_knowledge_base == "secondary"`、`refused is False`、至少 1 条 citation、citation source 包含 `secondary` 或 `e2e_support.md`，答案包含 `2`、`hour`、`urgent` 中至少一个。
- unknown question 断言 `refused is True` 或 citations 为空，不断言固定拒答文本。

Escalation:
- 如果现有 API 响应字段与方案不一致，停止并报告实际字段，不修改 API 合同。
- 如果 Docker 启动暴露实现 bug，不在本 WP 内修 API；报告给主 agent 分派修复。

Stop condition:
- 最多实现一个测试文件；不进入重复 Docker debug loop。

Output format:
- Summary:
- Evidence:
- Observed vs expected:
- Root cause or leading hypothesis:
- Files changed:
- Verification:
- Risks / unverified items:
- Ownership deviations:
- Escalation needed:

### WP3: Pytest Marker And Run Documentation

Tier: worker54mini

Ownership:
- Read/write: `pyproject.toml`, `README.md`
- Read-only: `tests/e2e/test_router_compose_live.py`, `.env.example`
- Forbidden: 不修改测试逻辑，不修改 Docker/API，不提交 `.env`

Task:
注册 `e2e` pytest marker，并在 README 中补充 live E2E 运行命令、费用/网络保护和 volume 保留说明。

Interfaces:
- Inputs: 用户 Implementation Notes。
- Dependencies: WP2 测试路径。
- Outputs: `pyproject.toml` marker 与 README 小节。

Acceptance:
- `pyproject.toml` 增加 marker，例如 `e2e: Docker Compose live tests using real OpenAI-compatible models`。
- README 包含 PowerShell 运行命令:
  ```powershell
  $env:KB_E2E_LIVE="1"
  pytest tests/e2e/test_router_compose_live.py -m e2e -s
  ```
- README 明确 `.env` 由本地用户提供，必须含 `KB_OPENAI_API_KEY`。
- README 明确测试结束运行 `docker compose down`，不删除 volume。
- README 明确该测试会产生真实模型 API 调用和潜在费用。

Escalation:
- 如果 README 已有同类 E2E 小节，追加到现有位置，不新建重复章节。

Stop condition:
- 只做 marker 与文档补充。

Output format:
- Summary:
- Evidence:
- Observed vs expected:
- Files changed:
- Verification:
- Risks / uncertainty:
- Ownership deviations:
- Escalation needed:

### WP4: Static And Non-Live Verification

Tier: worker54mini

Ownership:
- Read/write: 无
- Read-only: 全项目
- Forbidden: 不修改文件，不设置 `KB_E2E_LIVE=1`，不启动 Docker，不调用真实模型

Task:
验证新增 E2E 在默认状态不会误触发真实模型或 Docker，并检查 Compose 配置和 pytest collection/marker 基本可用。

Interfaces:
- Inputs: WP1、WP2、WP3 输出。
- Dependencies: WP1-WP3。
- Outputs: 验证报告。

Acceptance:
- `docker compose config --quiet` exit code 0。
- `pytest tests/e2e/test_router_compose_live.py -m e2e -q` 在未设置 `KB_E2E_LIVE=1` 时 skip，exit code 0。
- `pytest --collect-only tests/e2e/test_router_compose_live.py -q` exit code 0。
- 报告不得声称 live E2E 已通过，除非真实运行过。

Escalation:
- 如果 pytest collection 失败，报告最小 traceback 和疑似文件；不直接修复。

Stop condition:
- 不执行 live E2E。

Output format:
- Summary:
- Evidence:
- Observed vs expected:
- Files changed:
- Verification:
- Risks / uncertainty:
- Ownership deviations:
- Escalation needed:

### WP5: Optional Live E2E Run

Tier: worker53

Ownership:
- Read/write: 无，除非主 agent 明确要求修复测试文件
- Read-only: 全项目、本地 `.env`
- Forbidden: 不删除 volume，不运行 `docker compose down -v`，不启动 Langflow，不修改 `.env`

Task:
在用户明确接受真实模型调用成本并确认 `.env` 可用时，执行 live E2E，采集命令、exit code 和 bounded logs。

Interfaces:
- Inputs: WP1-WP4 已集成代码。
- Dependencies: WP4 通过；本地 `.env` 存在且含 API key。
- Outputs: live 验证报告。

Acceptance:
- 命令:
  ```powershell
  $env:KB_E2E_LIVE="1"
  pytest tests/e2e/test_router_compose_live.py -m e2e -s
  ```
- exit code 0 时报告 live E2E 通过。
- exit code 非 0 时报告失败场景、关键 stdout/stderr、`kb-api` tail logs 和 `kb_chroma_data` 卷检查是否已输出。
- 运行结束后确认没有由本测试残留的 running Compose 服务，除非用户要求保留。

Escalation:
- 如果失败原因是网络、API key、余额、限流或 Docker Desktop 状态，作为环境阻塞上报，不修改代码。
- 如果失败原因是明确测试断言过严，建议交回 WP2 收窄断言。

Stop condition:
- 最多一次 live run；不进行多轮真实模型重试。

Output format:
- Summary:
- Evidence:
- Observed vs expected:
- Root cause or leading hypothesis:
- Files changed:
- Verification:
- Risks / unverified items:
- Ownership deviations:
- Escalation needed:

## Recommended Execution Order

1. WP0 read-only contract scout。
2. WP1 fixtures 与 WP2 test implementation 可在 WP0 后顺序执行；WP2 依赖 fixtures 的目标路径。
3. WP3 marker/docs 可与 WP2 后半段并行，但最终需引用实际测试路径。
4. WP4 非 live 验证由独立 worker 执行。
5. WP5 仅在用户明确同意真实模型调用成本和本地环境具备条件时执行。

## Integration Plan

- 主 agent 先审查 WP1 fixture 是否足够短且事实唯一。
- 主 agent 审查 WP2 是否只依赖公开 HTTP API，不 import 内部 app 对象绕过 Compose。
- 主 agent 检查所有 subprocess 命令使用 list args，不拼接 shell 字符串。
- 主 agent 检查 `finally` 中只执行 `docker compose down`，没有 `-v`。
- 主 agent 检查 README 声明不超过实际验证结果。
- 如 worker 修改 ownership 外文件，必须单独解释并由主 agent 审核是否保留。

## Final Validation

Minimum non-live gates:

```powershell
docker compose config --quiet
pytest --collect-only tests/e2e/test_router_compose_live.py -q
pytest tests/e2e/test_router_compose_live.py -m e2e -q
```

Optional live gate:

```powershell
$env:KB_E2E_LIVE="1"
pytest tests/e2e/test_router_compose_live.py -m e2e -s
```

Observed-vs-expected reporting:

- Expected: non-live tests collect and skip without Docker/model calls。
- Observed: command exit codes and skip/fail/pass counts。
- Decision: accept non-live implementation, or escalate failing WP。

Live reporting:

- Expected: compose config ok, health ok, both ingests write chunks, router selects correct KB, unknown question refuses or has no citations。
- Observed: pytest result plus bounded compose logs on failure。
- Decision: accepted only if live command exit code is 0。

## Worker Prompt Templates

### worker53 Implementation / Live Verification Prompt

```text
You are worker53, a GPT-5.4 high-confidence execution worker.
You are not alone in the codebase. Do not revert user edits or edits from other workers.

Workspace:
C:\playground\langchain_knowledge_base

Ownership:
<paste one WP ownership block>

Task:
<paste one WP task block>

Interfaces:
- Read-only context: files named in the WP.
- Forbidden: scope outside the WP forbidden block.
- Dependencies: <name prior WP outputs, or none>.

Acceptance:
<paste WP acceptance block>

Constraints:
- Follow existing project patterns.
- Keep changes scoped.
- Avoid unrelated refactors.
- Diagnose errors before changing code.
- Do not claim acceptance unless the matching gate passed.
- Do not delete Docker volumes.
- Do not call real models unless this WP explicitly permits live execution.

Execution:
Run needed commands yourself, inspect stdout/stderr, diagnose failures before changing code, make scoped edits when appropriate, and verify the result.

Output:
- Summary:
- Evidence:
- Observed vs expected:
- Root cause or leading hypothesis:
- Files changed:
- Verification:
- Risks / unverified items:
- Ownership deviations:
- Escalation needed:
```

### worker54mini Scout / Docs / Verification Prompt

```text
You are worker54mini, a GPT-5.4 Mini execution worker.
You are not alone in the codebase. Do not revert user edits or edits from other workers.

Role:
Low-cost scout, verifier, summarizer, docs/config checker, or trivial-patch worker. Prefer evidence over broad judgment.

Workspace:
C:\playground\langchain_knowledge_base

Ownership:
<paste one WP ownership block>

Task:
<paste one WP task block>

Interfaces:
- Read-only context: files named in the WP.
- Forbidden: scope outside the WP forbidden block.
- Dependencies: <name prior WP outputs, or none>.

Acceptance:
<paste WP acceptance block>

Constraints:
- Keep output compact.
- Do not broaden scope.
- Do not run Docker, GUI, long-running runtime commands, or real model calls unless explicitly assigned.
- If diagnosis or fix becomes non-obvious, stop and escalate instead of guessing.

Execution:
Run needed commands yourself, inspect stdout/stderr, and summarize key facts. Do not paste long logs.

Output:
- Summary:
- Evidence:
- Observed vs expected:
- Files changed:
- Verification:
- Uncertainty / escalation trigger:
- Ownership deviations:
```

