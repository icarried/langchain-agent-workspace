# Agent Workspace

这个工作空间用于开发多个 LangChain / LangGraph 智能体项目，并让 Codex 或其他 Agent 能快速理解目录、环境、任务状态、密钥来源和调试入口。

## 快速入口

1. 先读 [AGENTS.md](./AGENTS.md)，了解协作规则和工作流。
2. 再读 [docs/workspace/WORKSPACE_BLUEPRINT.md](./docs/workspace/WORKSPACE_BLUEPRINT.md)，了解目录与信息放置约定。
3. 创建开发环境时读 [docs/development/CONDA_LANGCHAIN_ENV.md](./docs/development/CONDA_LANGCHAIN_ENV.md)。
4. 启动、调试、排错时读 [docs/development/RUN_AND_DEBUG.md](./docs/development/RUN_AND_DEBUG.md)。
5. 拆解和推进任务时维护 [.agents/tasks/TASK_BOARD.md](./.agents/tasks/TASK_BOARD.md)。
6. 遇到问题时记录到 [docs/operations/PROBLEM_LOG.md](./docs/operations/PROBLEM_LOG.md)。
7. 新增或查找智能体时维护 [docs/workspace/AGENT_REGISTRY.md](./docs/workspace/AGENT_REGISTRY.md)。
8. 部署或接入统一 OpenAI-compatible 入口时读 [docs/development/AGENT_GATEWAY.md](./docs/development/AGENT_GATEWAY.md)。

## 当前状态

- 已建立 Agent 可读的工作空间纲领、目录规范和任务台账。
- 已整理本地 API key 到 `.env.local`，并将原始 key 文件归档到 `secrets/raw/unorganized-api-keys/`。
- 已提供 LangChain / LangGraph conda 环境说明和 `environment.yml`。
- 用户已创建 conda 环境 `langchain`，后续开发直接 `conda activate langchain`。
- 本工作空间将承载多个智能体，新增智能体时应在任务台账和源码说明中登记。
- 已建立多智能体登记表，用于记录每个智能体的用途、路径、入口和状态。
- 已创建 `tender-format-review` 招标文件格式审查智能体，并沉淀 `.codex/skills/langchain-agent-builder/` 作为后续 LangChain 智能体创建 skill。
- 已创建 `resume-review` 单份简历审查智能体和 `batch_resume_review_llm` 批量简历筛选、评分与排序智能体；旧 `batch_resume_review` 包仅保留兼容转发。
- 已建立统一 OpenAI-compatible 网关：生产环境只发布 `8004`，按模型 ID 路由到六个相互隔离的 worker，本机开发可由单命令监管启动。
- 已将知识库重做为工作区级 `src/knowledge_base/` 可复用核心，按 agent namespace 和知识库名称隔离 Chroma 数据，不兼容旧 primary/secondary 数据。

## 推荐目录

```text
.
├── .agents/                 # Agent 协作规则、任务板、交接记录
├── docs/                    # 工作空间、开发、运维与问题记录
├── secrets/                 # 本地密钥归档，仅本机使用，不提交
├── src/                     # 智能体源码
├── tests/                   # 测试
├── .env.example             # 环境变量模板，可提交
├── .env.local               # 本地真实密钥，不提交
├── environment.yml          # conda 环境定义
└── AGENTS.md                # Agent 进入工作区后的第一阅读文件
```
