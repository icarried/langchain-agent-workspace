# Agent Registry

用于登记本工作空间中的多个智能体。每新增一个智能体，都应在这里记录用途、路径、入口、依赖和当前状态，方便人和 Agent 快速接手。

## 登记规则

- 每个智能体使用一个稳定名称，建议小写英文和短横线，例如 `research-agent`。
- 源码建议放在 `src/agents/<agent_name>/`。
- 启动和调试方式应同步写入 `docs/development/RUN_AND_DEBUG.md`。
- 相关任务应同步写入 `.agents/tasks/TASK_BOARD.md`。
- 不在本文件记录真实 API key，只记录需要的环境变量名。

## 智能体列表

### langchain-knowledge-base

- 状态: Ready
- 用途: Code-first 本地知识库 RAG 智能体，支持本地 PDF、DOCX、Markdown、TXT 文档入库、检索问答、来源引用、无依据拒答、基础 eval，以及 Langflow 演示 UI。
- 源码路径: `src/agents/langchain_knowledge_base/`
- 子项目定位: 保持可分离的独立智能体项目；运行、测试、打包和 Docker Compose 均以 `src/agents/langchain_knowledge_base/` 为工作目录，不从工作区根目录导入运行。
- API 入口: 在智能体目录下运行 `uvicorn kb_api.main:app --host 0.0.0.0 --port 8008`，接口包含 `GET /health`、`POST /ingest`、`POST /v1/retrieval`、`GET /v1/models`、`POST /v1/chat/completions`，模型 ID `langchain-knowledge-base-agent`。
- Docker 入口: 在智能体目录下运行 `docker compose up --build`；默认启动 `kb-api` 和 `langflow`，不启动独立 Chroma 服务。
- 调试方式: 先复制 `src/agents/langchain_knowledge_base/.env.example` 为同目录 `.env`，把文档放入 `data/docs/`、`data/docs/primary/` 或 `data/docs/secondary/`，启动 API 后手动调用 `/ingest`，再调用 `/v1/retrieval` 或 `/v1/chat/completions`。
- 向量存储: 使用 Chroma `PersistentClient` 本地持久化；非 Docker 默认目录为 `data/chroma/`，Compose 内为 `/app/data/chroma`，通过命名卷 `kb_chroma_data` 保存。`docker compose down` 不删除向量库，只有 `docker compose down -v` 会重置 Compose 持久化数据。
- 需要的环境变量: `KB_OPENAI_API_KEY`；可选 `KB_OPENAI_BASE_URL`、`KB_CHAT_MODEL`、`KB_EMBEDDING_API_KEY`、`KB_EMBEDDING_BASE_URL`、`KB_EMBEDDING_MODEL`、`KB_DOCS_DIR`、`KB_CHROMA_PERSIST_DIR`、`KB_CHROMA_COLLECTION`、`KB_TOP_K`、`KB_MIN_RELEVANCE_SCORE`，以及 primary/secondary 知识库名称、目录、collection 和 keywords 配置。
- 关联任务: T-027
- 备注: 当前首版不包含鉴权、权限过滤、自动监听入库、生产级文档版本管理或 live Docker 真实模型 E2E。Langflow 只作为 demo/debug HTTP UI，不承载核心 RAG 逻辑。

### batch-resume-review

- 状态: Ready
- 用途: 一次审查多份 PDF、DOC、DOCX、MD 或 TXT 简历，强制筛除提示词注入和明确硬条件不符者，对其余候选人统一评分排序，并附加人工复核标记。
- 源码路径: `src/agents/batch_resume_review/`
- 运行入口: `python -m src.agents.batch_resume_review review <resume-a> <resume-b> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.batch_resume_review.mcp_server`；HTTP `python -m src.agents.batch_resume_review.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp`；tool 名称 `review_resumes`。
- API 入口: `uvicorn src.agents.batch_resume_review.api:app --reload --port 8006`，主接口 `POST /review`。
- 调试方式: 先用多份本地测试夹具运行 `--dry-run`，再接入模型验证筛除和排序；MCP 接收 `resumes` 文件列表和 `job_description_text`。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `BATCH_RESUME_REVIEW_MODEL`、`BATCH_RESUME_REVIEW_BASE_URL`、`BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS`、`BATCH_RESUME_REVIEW_MAX_REMOTE_FILE_BYTES`、`BATCH_RESUME_REVIEW_REMOTE_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MODEL`、`BATCH_RESUME_REVIEW_OCR_BASE_URL`、`BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MAX_PAGES`。
- 独立打包: `python scripts/package_agent_standalone.py --agent batch_resume_review --output-dir dist`，产物可脱离工作区运行。
- 关联任务: T-016、T-019、T-022、T-023
- 备注: REST API 的 `resume_paths` 支持服务端路径和 MinIO HTTP(S) 预签名 URL，并对远程读取实施超时、大小上限和可选主机白名单。筛除名单不参与排名，待复核候选人保留排名并同时出现在复核项中。报告显示简历原文姓名和文件名。CLI/API/MCP 均接受 PDF/DOC/DOCX/MD/TXT；扫描件按需使用百炼 OCR。正式审查加载智能体包内 `references/universities/` 高校参照。

### batch-resume-review-llm

- 状态: Ready
- 用途: 隔离复制 `batch-resume-review`，作为 Dify/FastGPT 自定义 OpenAI-compatible LLM 节点的流式模型适配器，输出批量简历审查进度和最终报告。
- 源码路径: `src/agents/batch_resume_review_llm/`
- 运行入口: `python -m src.agents.batch_resume_review_llm review <resume-a> <resume-b> --job-description <jd.txt> --output <report.md>`
- OpenAI-compatible 入口: `uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006`，模型 ID `batch-resume-review-agent`，接口 `GET /v1/models`、`POST /v1/chat/completions`。
- MCP 入口: stdio `python -m src.agents.batch_resume_review_llm.mcp_server`；HTTP `python -m src.agents.batch_resume_review_llm.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp`；tool 名称 `review_resumes`。
- API 入口: `uvicorn src.agents.batch_resume_review_llm.api:app --reload --port 8006`，主接口 `POST /review`。
- 调试方式: 先用 `/v1/chat/completions` 的 `dry_run=true` 验证 Dify/FastGPT 模型接入和流式输出，再接入正式模型。
- 需要的环境变量: 同 `batch-resume-review`。
- 关联任务: T-024
- 备注: 本智能体与原 `batch-resume-review` 沿用相同端口，二者不要同时启动；复制隔离用于避免影响原生产可用入口。

### resume-review

- 状态: Ready
- 用途: 审查人力部门收到的 DOCX、文本型 PDF 和 TXT 简历，输出基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配评分和面试追问建议。
- 源码路径: `src/agents/resume_review/`
- 运行入口: `python -m src.agents.resume_review review <resume> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.resume_review.mcp_server`；HTTP `python -m src.agents.resume_review.mcp_server --transport http --host 127.0.0.1 --port 8003 --path /mcp`；tool 名称 `review_resume`。
- API 入口: `uvicorn src.agents.resume_review.api:app --reload --port 8004`，主接口 `POST /review`。
- 调试方式: 先运行 `--dry-run` 验证简历解析、分块和 JD 输入，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `RESUME_REVIEW_MODEL`、`RESUME_REVIEW_BASE_URL`。
- 关联任务: T-015
- 备注: 第一版支持文本型 PDF，不支持扫描件 OCR；岗位 JD 可选，未提供 JD 时不生成匹配分，避免伪造岗位匹配依据。审查事项按 Markdown 文件拆分，正式 LLM 审查按基本条件/筛选条件/专业条件三个维度并行调用后汇总；学历维度默认加载 `src/reference_data/universities/` 高校参照。

### tender-format-review

- 状态: Ready
- 用途: 审查大型中文招标文件 `.docx` 的格式、章节、表格和跨章节一致性问题，输出 Markdown 审查报告。
- 源码路径: `src/agents/tender_format_review/`
- 运行入口: `python -m src.agents.tender_format_review review <docx> --review-guide <md> --catalog <txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.tender_format_review.mcp_server`；HTTP `python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp`；tool 名称 `review_tender_format`。
- API 入口: `uvicorn src.agents.tender_format_review.api:app --reload --port 8001`，主接口 `POST /review`。
- OpenAI-compatible 入口: `uvicorn src.agents.tender_format_review.openai_compatible_api:app --host 0.0.0.0 --port 8007`，模型 ID `tender-format-review-agent`，接口 `GET /v1/models`、`POST /v1/chat/completions`。
- 调试方式: 先运行 `--dry-run` 验证 docx 解析、分块和输出路径，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `TENDER_REVIEW_MODEL`、`TENDER_REVIEW_BASE_URL`、`TENDER_REVIEW_MAX_REMOTE_FILE_BYTES`、`TENDER_REVIEW_REMOTE_TIMEOUT_SECONDS`。
- 关联任务: T-009、T-011、T-012、T-026
- 备注: 对 10 万字以上文件默认采用“解析元素 -> 章节/长度分块 -> 分块审查 -> 汇总复核”，不依赖整篇一次放入上下文。OpenAI-compatible 入口用于 Dify/FastGPT LLM 节点流式输出，可从 prompt 的“招标文件”区块读取服务端路径或 HTTP(S) `.docx` 链接。Codex 后台起常驻 HTTP MCP 时，优先直接调用 `C:\Users\Lenovo\.conda\envs\langchain\python.exe`，不要依赖 `conda run`；详见 `docs/development/RUN_AND_DEBUG.md` 和 `docs/operations/PROBLEM_LOG.md` 的 2026-06-17 记录。

## 模板

```text
### <agent_name>

- 状态: Planned / In Development / Ready / Deprecated
- 用途:
- 源码路径: `src/agents/<agent_name>/`
- 运行入口:
- 调试方式:
- 需要的环境变量:
- 关联任务:
- 备注:
```

