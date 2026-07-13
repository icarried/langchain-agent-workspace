# Handoff: LangChain + Langflow 知识库智能体

> Status note (2026-06-30): 该文件是导入前交接记录。当前已实现首版 API/RAG/eval，并决定使用 Chroma `PersistentClient` 本地持久化；Docker Compose 默认不启动独立 Chroma 服务。最新运行方式以 `README.md` 为准。

## 当前目标

构建一个以 AI 编程工具（Codex 类 agent）为主要开发方式的知识库智能体项目。

用户明确表示：在使用 Dify 时发现图形化开发工具不好用，因此希望项目结构最大化利用 AI 编程能力，而不是依赖图形化编排。

## 已确定方案

采用 **Code-first 架构**：

- 核心逻辑使用 LangChain 代码实现。
- 首版只做可靠的 RAG 问答。
- Langflow 仅作为演示/调试 UI，不承载核心业务逻辑。
- 向量库使用本地 Chroma。
- 模型使用 OpenAI 兼容 API。
- 知识源首版为本地文档。
- 回答必须带来源引用。
- 入库采用手动命令触发。
- 运行方式采用 Docker Compose。

## 推荐项目结构

```text
.
├── AGENTS.md
├── docker-compose.yml
├── .env.example
├── data/
│   └── docs/
├── kb_api/
│   ├── main.py
│   ├── settings.py
│   ├── schemas.py
│   └── rag/
│       ├── ingest.py
│       ├── loaders.py
│       ├── chunking.py
│       ├── retriever.py
│       └── answer.py
├── prompts/
│   └── rag_answer.md
├── tests/
├── evals/
│   ├── questions.yml
│   └── run.py
├── docs/
│   └── adr/
└── langflow/
    └── flows/
```

## 首版接口

- `GET /health`
  - 检查 API、Chroma、模型配置状态。

- `POST /ingest`
  - 扫描 `data/docs/`。
  - 支持 PDF、DOCX、Markdown、TXT。
  - 执行加载、切分、embedding、写入 Chroma。

- `POST /v1/chat/completions`
  - 输入用户问题。
  - 从 Chroma 检索相关 chunk。
  - 调用 OpenAI 兼容 Chat API。
  - 返回答案和 citations。

## 关键工程原则

- Prompt 必须放在 `prompts/`，不要写死在代码或 Langflow 节点里。
- 所有请求、响应、引用结构使用 Pydantic schema。
- Langflow flow JSON 可以保存，但不能作为核心业务逻辑来源。
- Codex 后续迭代应优先修改源码、测试、eval、ADR，而不是修改图形节点。
- 每个行为都应有自动化验证，尤其是：
  - 检索是否命中。
  - 引用是否正确。
  - 无依据时是否拒答。
  - 空知识库和配置错误是否有清晰错误。

## 建议测试

- `pytest`
  - chunking 单元测试。
  - loader 单元测试。
  - citation 格式测试。
  - empty corpus 行为测试。

- `python -m evals.run`
  - 使用 `evals/questions.yml` 跑 golden questions。
  - 验证答案命中率、拒答行为、引用质量。

- Docker 验证：
  - `docker compose up`
  - 检查 `kb-api`、`langflow` 健康状态，并确认 Chroma 本地持久化目录或 Compose 卷存在。

## Langflow 定位

Langflow 只做演示/调试：

- Flow 输入用户问题。
- HTTP 调用 `kb-api /v1/chat/completions`。
- 展示 answer 和 citations。
- 不在 Langflow 中实现复杂 RAG、Prompt、工具调用或状态逻辑。

原因：图形化配置不利于 Codex review、diff、重构、测试和长期维护。

## 需要避免

- 不要把核心业务逻辑放进 Langflow 图。
- 不要追求 Langflow 和 LangChain 代码一键互转。
- 不要首版引入多智能体、复杂 LangGraph、权限系统、网页抓取、文件夹监听。
- 不要在启动时自动入库，避免隐式修改向量库。

## 后续可扩展方向

- 如果 RAG 问答稳定后需要复杂流程，可引入 LangGraph。
- 如果 Chroma 不满足部署需求，可迁移到 Qdrant 或 pgvector。
- 如果要接业务系统，可新增 tool 层，但仍保持代码优先。
- 如果要生产化，可补充鉴权、权限过滤、文档版本管理和增量入库。

## Suggested Skills

- `orchestrator-workers`
  - 用于后续拆分实现任务，例如 API、RAG、Docker、测试、Langflow demo flow。

- `tdd`
  - 用于先写检索、引用、拒答相关测试，再实现功能。

- `diagnose`
  - 用于排查 Chroma、LangChain、模型 API 或 Docker 启动问题。

- `to-issues`
  - 用于把该方案拆成可并行处理的实现 issue。

## 当前状态

尚未写入代码或项目文件。当前只完成了架构规划和交接内容整理。
