# LangChain + Langflow 知识库智能体实现拆分

> Status note (2026-06-30): 首版实现已收敛为独立子项目，并决定使用 Chroma `PersistentClient` 本地持久化。Docker Compose 默认只启动 `kb-api` 和 `langflow`，不再启动独立 `chroma` 服务；下文中关于独立 Chroma 服务的拆分项仅保留为历史计划记录。

## Mission

构建一个 code-first 的本地知识库 RAG 智能体：核心业务逻辑由 LangChain + FastAPI 源码承载，Langflow 只做演示/调试 UI，首版完成本地文档入库、检索问答、来源引用、基础评测和 Docker Compose 运行。

## Success Criteria

- `GET /health` 能报告 API、Chroma、模型配置的可用状态。
- `POST /ingest` 能从 `data/docs/` 手动入库 PDF、DOCX、Markdown、TXT。
- `POST /v1/chat/completions` 能基于 Chroma 检索回答，并返回 OpenAI-compatible chat completion。
- 无相关依据时按 prompt 规则拒答，不编造来源。
- Prompt 位于 `prompts/`，请求/响应/citation 使用 Pydantic schema。
- Langflow flow 只通过 HTTP 调用 `kb-api /v1/chat/completions`，不承载核心 RAG 逻辑。
- `pytest`、`python -m evals.run`、Docker Compose 健康检查有明确通过/失败信号。

## Scope

- In scope: Python API、RAG ingest/retrieval/answering、Prompt、tests、evals、Docker Compose、Langflow demo flow、ADR/docs。
- Out of scope: 多智能体、LangGraph、鉴权、权限过滤、网页抓取、文件夹监听、启动自动入库、生产级文档版本管理。

## Claim Boundaries

- Allowed to say: 首版 RAG 问答链路、引用结构、手动入库和 Docker 本地运行已实现并通过指定验证。
- Not allowed to say: 生产可用、权限安全、跨租户隔离、Langflow 与 LangChain 双向同步、复杂工作流已支持，除非后续另行实现并验证。

## Signals

- 文件信号: 项目结构、API/RAG 模块、prompt、tests/evals、Docker/Langflow artifacts 存在。
- 命令信号: `pytest`、`python -m evals.run`、`docker compose up` 或健康检查命令 exit code。
- 行为信号: 空知识库、配置错误、无依据问题、带来源回答都有可观察响应。
- 质量信号: citations 指向文档来源和 chunk 元数据，golden questions 有明确命中/拒答结果。

## Disturbances

- OpenAI 兼容 API key/base URL 未配置或网络不可达。
- Chroma 版本/API 变化导致初始化或持久化差异。
- PDF/DOCX loader 依赖在容器内缺失。
- Docker 镜像拉取或依赖安装受网络影响。
- Langflow 版本更新导致 flow JSON schema 或 HTTP component 行为变化。

## Control Actions

- 先实现 mockable 的核心 RAG 单元，再接真实模型和 Docker。
- 对网络/模型相关验证使用配置检查、mock、或明确跳过条件。
- Worker54mini 用于文件盘点、测试/文档/配置一致性检查。
- Worker53 用于非平凡代码实现、失败诊断、Docker/Langflow 集成。
- 任一 worker 发现 scope 外需求时停止并上报，不扩展到权限、LangGraph 或自动监听。

## Local Critical Path

1. 主 agent 确认最终目录结构和依赖栈。
2. 先落项目骨架、schema、settings 和测试入口，给后续 worker 稳定接口。
3. 按模块并行实现 loader/chunking、retriever/answer、API、eval/Docker/Langflow。
4. 主 agent 汇总 patch，运行最小集成验证，修正接口不一致。

## Work Packages

### WP0: 项目骨架与依赖基线

Tier: worker53

Ownership:
- Read/write: `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`, `AGENTS.md`, package `__init__.py` files
- Read-only: `handoff-langchain-langflow-kb-agent.md`
- Forbidden: 不实现 RAG 业务逻辑细节，不写 Langflow flow

Task:
创建可运行的 Python 项目骨架，固定首版依赖、入口命令、Docker 服务边界和本地目录挂载。

Acceptance:
- 项目目录与 handoff 推荐结构一致。
- API、Chroma、Langflow 在 Compose 中有清晰服务名、端口和 volume。
- `.env.example` 覆盖 OpenAI 兼容 API、Chroma、collection、模型配置。
- 能运行基础导入或 `python -m compileall kb_api`。

Escalation:
- 如果依赖版本冲突或 Docker 镜像不可拉取，停止并报告候选版本与失败日志。

### WP1: Pydantic Schema、Settings 与健康检查

Tier: worker53

Ownership:
- Read/write: `kb_api/main.py`, `kb_api/settings.py`, `kb_api/schemas.py`, `tests/test_health.py`
- Read-only: `.env.example`, `docker-compose.yml`
- Forbidden: 不实现 ingest/chat 深层逻辑，只定义接口壳和健康检查

Task:
实现 FastAPI app、配置加载、请求/响应/citation schema、`GET /health`。

Acceptance:
- `GET /health` 返回 API 状态、Chroma 配置状态、模型配置状态。
- schema 覆盖 ingest/chat/citation/error 场景。
- 配置缺失时错误清晰，不在 import 阶段崩溃。
- `pytest tests/test_health.py` 通过。

Escalation:
- 如果 settings 需要引入额外配置库，先说明理由，不扩大到复杂配置系统。

### WP2: 文档加载与切分

Tier: worker53

Ownership:
- Read/write: `kb_api/rag/loaders.py`, `kb_api/rag/chunking.py`, `tests/test_loaders.py`, `tests/test_chunking.py`, `data/docs/.gitkeep`
- Read-only: `kb_api/schemas.py`
- Forbidden: 不写 Chroma 写入、不调用 LLM

Task:
实现本地 PDF、DOCX、Markdown、TXT 加载，统一输出 document/chunk 元数据，并实现稳定 chunking。

Acceptance:
- 每类 loader 有至少一个单元测试或 fixture 覆盖。
- chunk metadata 至少包含 source、chunk index，可用于 citations。
- 空文件、未知扩展名、不可读文件有明确行为。
- `pytest tests/test_loaders.py tests/test_chunking.py` 通过。

Escalation:
- 如果 PDF/DOCX 解析依赖导致安装失败，报告替代库和失败原因。

### WP3: Chroma 入库链路

Tier: worker53

Ownership:
- Read/write: `kb_api/rag/ingest.py`, `tests/test_ingest.py`
- Read-only: `kb_api/rag/loaders.py`, `kb_api/rag/chunking.py`, `kb_api/settings.py`, `kb_api/schemas.py`
- Forbidden: 不实现 chat answer 生成，不改 loader/chunking 除非接口缺陷阻塞

Task:
实现手动入库服务：扫描 `data/docs/`，加载、切分、embedding、写入本地 Chroma collection，并返回入库统计。

Acceptance:
- 支持重复运行的合理行为有定义：覆盖、追加或基于文档 ID 去重，需在代码/测试中一致。
- 空目录返回清晰结果，不隐式成功写入假数据。
- embedding provider 通过 settings 注入，测试可 mock。
- `pytest tests/test_ingest.py` 通过。

Escalation:
- 如果 Chroma persistence 行为与预期不一致，先提交诊断报告，不做大范围重构。

### WP4: Retriever 与 Answer Chain

Tier: worker53

Ownership:
- Read/write: `kb_api/rag/retriever.py`, `kb_api/rag/answer.py`, `prompts/rag_answer.md`, `tests/test_retriever.py`, `tests/test_answer.py`, `tests/test_citations.py`
- Read-only: `kb_api/schemas.py`, `kb_api/settings.py`
- Forbidden: 不实现 HTTP routes，不修改 ingest 写入策略

Task:
实现检索、prompt 加载、OpenAI 兼容 chat 调用、拒答规则、citations 组装。

Acceptance:
- answer 不硬编码 prompt，必须从 `prompts/rag_answer.md` 加载。
- citations 从检索 chunk metadata 生成，格式由 schema 约束。
- 无命中或低置信证据时拒答。
- 模型调用可在测试中 mock。
- `pytest tests/test_retriever.py tests/test_answer.py tests/test_citations.py` 通过。

Escalation:
- 如果 LangChain wrapper 与 OpenAI 兼容 API 参数不匹配，报告最小复现和建议替代调用方式。

### WP5: API Routes 集成

Tier: worker53

Ownership:
- Read/write: `kb_api/main.py`, `tests/test_api_ingest_chat.py`
- Read-only: `kb_api/rag/*`, `kb_api/schemas.py`, `kb_api/settings.py`
- Forbidden: 不重写 RAG 模块内部实现

Task:
接入 `POST /ingest`、`POST /v1/retrieval` 和 `POST /v1/chat/completions`，统一错误响应和 schema 校验。

Acceptance:
- `/ingest` 调用 WP3 入库服务并返回统计。
- `/v1/chat/completions` 调用 WP4 answer chain 并返回 OpenAI-compatible chat completion。
- 空知识库、配置错误、模型错误有可测试响应。
- `pytest tests/test_api_ingest_chat.py` 通过。

Escalation:
- 如果 RAG 模块接口不足，提出最小接口变更，不跨文件重写。

### WP6: Eval Harness 与 Golden Questions

Tier: worker54mini

Ownership:
- Read/write: `evals/questions.yml`, `evals/run.py`, `tests/test_evals.py`
- Read-only: `kb_api/schemas.py`, `kb_api/rag/answer.py`
- Forbidden: 不改 RAG 实现，不调用真实付费模型作为默认测试

Task:
实现可重复的 golden question 评测入口，验证命中率、拒答行为、引用质量。

Acceptance:
- `python -m evals.run` 能读取 YAML 并输出结构化 summary。
- 默认可用 fake/mock API 或要求显式环境变量才调用真实 API。
- 至少包含正例、无依据拒答、citation 检查三类样例。
- `pytest tests/test_evals.py` 通过。

Escalation:
- 如果真实模型调用是必须条件，停止并要求主 agent 决策。

### WP7: Docker Compose 集成验证

Tier: worker53

Ownership:
- Read/write: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `scripts/` 下项目本地验证脚本
- Read-only: `.env.example`, `kb_api/*`
- Forbidden: 不改业务逻辑，除非容器启动暴露出明确路径/import 缺陷

Task:
完成 API、Chroma、Langflow 的容器化运行和健康检查路径。

Acceptance:
- `docker compose config` 通过。
- `docker compose up` 后 `kb-api`、`langflow` 有明确健康状态或可探测端口，Chroma 持久化卷可确认存在。
- volume 映射覆盖 `data/docs/` 与 Chroma persistence。
- 不在容器启动时自动入库。

Escalation:
- 网络拉取失败时记录镜像名、命令、exit code，不反复重试。

### WP8: Langflow Demo Flow

Tier: worker53

Ownership:
- Read/write: `langflow/flows/kb_chat_demo.json`, `docs/langflow-demo.md`
- Read-only: `kb_api/schemas.py`, `docker-compose.yml`
- Forbidden: 不在 Langflow 中实现 RAG、Prompt、retriever、工具调用或状态逻辑

Task:
创建一个只调用 `kb-api /v1/chat/completions` 的 Langflow 演示 flow，并记录导入/运行方式。

Acceptance:
- flow 输入用户问题，HTTP 调用 `/v1/chat/completions`，展示 `choices[0].message.content`。
- docs 明确 Langflow 是 demo/debug UI，不是业务逻辑来源。
- 不复制 prompt 到 Langflow 节点。

Escalation:
- 如果 Langflow JSON schema 不稳定，保留最小 docs 和手动配置说明，不硬凑不可导入 JSON。

### WP9: ADR、使用文档与 Claim Review

Tier: worker54mini

Ownership:
- Read/write: `docs/adr/0001-code-first-rag.md`, `README.md`
- Read-only: 全项目
- Forbidden: 不改实现代码

Task:
记录 code-first 决策、Langflow 定位、首版运行方式、验证命令和非目标。

Acceptance:
- README 包含 setup、ingest、chat、test、eval、docker compose 命令。
- ADR 解释为什么 Langflow 不承载核心逻辑。
- 文档声明不超过已实现和已验证范围。

Escalation:
- 如果实现状态与文档目标不一致，按实际状态标注 pending，不美化。

### WP10: 独立验证与集成验收

Tier: worker54mini

Ownership:
- Read/write: 无，默认 read-only
- Read-only: 全项目
- Forbidden: 不修改文件，不启动长时间后台服务；Docker 只在明确授权窗口内运行

Task:
独立运行最终验证清单，比较 expected vs observed，输出验收报告。

Acceptance:
- 报告 `pytest`、`python -m evals.run`、`docker compose config`、API smoke check 的命令和 exit code。
- 明确哪些验证通过、哪些跳过、哪些失败。
- 失败时给出最小 stderr/stdout 事实和建议分派给哪个 WP 返工。

Escalation:
- 任一失败原因不明显时，停止在 evidence pass，不直接修复。

## Recommended Execution Order

1. WP0 项目骨架与依赖基线。
2. WP1 schema/settings/health，建立稳定 API 合同。
3. 并行执行 WP2 loader/chunking 与 WP4 answer/retriever 的 mockable 部分；WP4 依赖 schema，不依赖真实 ingest。
4. WP3 入库链路，接上 WP2 输出。
5. WP5 API routes 集成，接上 WP3/WP4。
6. WP6 eval harness 与 WP9 docs/ADR 可并行补齐。
7. WP7 Docker Compose 与 WP8 Langflow demo。
8. WP10 独立验证，失败则按责任 WP 返工一次。

## Integration Plan

- 主 agent 合并时优先检查 schema 接口是否一致，再检查 RAG 模块间调用。
- 多 worker 输出冲突时，以测试和 schema 为准，不以实现偏好为准。
- 任何 worker 修改 ownership 外文件，主 agent 必须单独审查原因。
- 先跑快速单元测试，再跑 eval，再跑 Docker。
- 最终报告必须区分已验证事实、跳过项和未实现后续方向。

## Final Validation

Minimum sufficient gates:

```powershell
python -m compileall kb_api
pytest
python -m evals.run
docker compose config
```

Docker runtime gate, when environment allows:

```powershell
docker compose up --build
```

API smoke examples:

```powershell
Invoke-RestMethod http://localhost:8008/health
Invoke-RestMethod -Method Post http://localhost:8008/ingest
Invoke-RestMethod -Method Post http://localhost:8008/v1/chat/completions -ContentType 'application/json' -Body '{"model":"langchain-knowledge-base-agent","messages":[{"role":"user","content":"..."}]}'
```

## Worker Prompt Templates

### worker53 Implementation Prompt

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
- Read-only context: handoff-langchain-langflow-kb-agent.md and dependency files named in the WP.
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

### worker54mini Scout / Verification Prompt

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
- Read-only context: handoff-langchain-langflow-kb-agent.md and dependency files named in the WP.
- Forbidden: scope outside the WP forbidden block.
- Dependencies: <name prior WP outputs, or none>.

Acceptance:
<paste WP acceptance block>

Constraints:
- Keep output compact.
- Do not broaden scope.
- Do not run GUI, long-running runtime commands, or destructive commands unless explicitly assigned.
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

