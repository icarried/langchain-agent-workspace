# Agent Registry

用于登记本工作空间中的多个智能体。每新增一个智能体，都应在这里记录用途、路径、入口、依赖和当前状态，方便人和 Agent 快速接手。

## 登记规则

- 每个智能体使用一个稳定名称，建议小写英文和短横线，例如 `research-agent`。
- 源码建议放在 `src/agents/<agent_name>/`。
- 启动和调试方式应同步写入 `docs/development/RUN_AND_DEBUG.md`。
- 相关任务应同步写入 `.agents/tasks/TASK_BOARD.md`。
- 不在本文件记录真实 API key，只记录需要的环境变量名。

## 统一部署入口

- OpenAI-compatible 生产入口统一为 `http://<host>:8008/v1`，模型由请求体 `model` 选择。
- `GET /v1/models` 只列出健康 worker。Compose 中每个 worker 独立监听内部 `8080`，不发布宿主机端口。
- 原 REST API、MCP 和独立 OpenAI-compatible 端口仅保留源码用于单智能体调试，不进入生产 Compose。
- 部署、鉴权、附件和知识库说明见 `docs/development/AGENT_GATEWAY.md`。

## 智能体列表

### image-generation

- 状态: In Development
- 用途: 对话式图片生成与编辑；Qwen3.5结合文本和图片改写提示词，无底图调用 `qwen-image`，有底图调用 `qwen-image-edit`，并自动沿用最近助手图片。
- 源码路径: `src/agents/image_generation/`
- 运行入口: `python -m src.agents.image_generation "<prompt>" --dry-run`
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `image-generation-agent`。
- 需要的环境变量: `GPU_STACK_BASE_URL`、`GPU_STACK_API_KEY`；可选图片模型、大小和超时覆盖变量。
- 关联任务: T-040
- 备注: 首版单图输入、单图输出；完整展示、持久化和连续编辑需要 AI 应用平台完成 `docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`。

### smart-resume-screening

- 状态: Ready
- 用途: 基于 FastGPT 导出工作流“智能简历筛选”的有效经验创建的结构化初筛智能体，按岗位基本信息、硬性条件、优先条件和淘汰条件对多份简历打分排序。
- 源码路径: `src/agents/smart_resume_screening/`
- 运行入口: `python -m src.agents.smart_resume_screening screen <resume-a> <resume-b> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.smart_resume_screening.mcp_server`；HTTP `python -m src.agents.smart_resume_screening.mcp_server --transport http --host 127.0.0.1 --port 8011 --path /mcp`；tool 名称 `screen_resumes`。
- API 入口: `uvicorn src.agents.smart_resume_screening.api:app --reload --port 8011`，主接口 `POST /screen`。
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `smart-resume-screening-agent`。
- 调试方式: 先用内置 `src/agents/smart_resume_screening/examples/` 执行 `--dry-run`，确认条件解析、候选人状态和排行榜；正式运行再接入 DeepSeek 或 DashScope/Qwen 整理报告。
- 需要的环境变量: 默认 `GPU_STACK_API_KEY`，旧 `DEEPSEEK_API_KEY` 仅兼容回退；DashScope provider 使用 `DASHSCOPE_API_KEY`。可选 `SMART_RESUME_SCREENING_MODEL`、`SMART_RESUME_SCREENING_BASE_URL`。
- 关联任务: T-030、T-031
- 备注: 本智能体定位为轻量结构化初筛配置器；复杂 OCR、远程 URL、高校参照、规则调整和独立打包仍优先使用 `batch-resume-review-llm`。OpenAI-compatible 入口用于 FastGPT/Dify LLM 节点流式输出，可从 prompt 的“岗位要求”“简历文件”区块、平台 `附件：` 列表或 OpenAI content parts 的 `file_url.url` 读取服务端路径或文件链接。

### official-document-review

- 状态: Ready
- 用途: 基于 FastGPT 导出工作流“公文优化”的有效经验创建的公文格式检查与优化智能体，检查文件是否符合《党政机关公文格式》GB/T 9704-2012 的基础版式和结构要求，并整理整改建议。
- 源码路径: `src/agents/official_document_review/`
- 运行入口: `python -m src.agents.official_document_review review <document> --document-type 通知 --output <report.md>`
- MCP 入口: stdio `python -m src.agents.official_document_review.mcp_server`；HTTP `python -m src.agents.official_document_review.mcp_server --transport http --host 127.0.0.1 --port 8010 --path /mcp`；tool 名称 `review_official_document`。
- API 入口: `uvicorn src.agents.official_document_review.api:app --reload --port 8010`，主接口 `POST /review`。
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `official-document-review-agent`。
- 调试方式: 先用内置 `src/agents/official_document_review/examples/示例通知.md` 执行 `--dry-run`，确认文件解析、确定性检查和报告结构；正式运行再接入 DeepSeek 或 DashScope/Qwen 美化报告。
- 需要的环境变量: 默认 `GPU_STACK_API_KEY`，旧 `DEEPSEEK_API_KEY` 仅兼容回退；DashScope provider 使用 `DASHSCOPE_API_KEY`。可选 `OFFICIAL_DOCUMENT_REVIEW_MODEL`、`OFFICIAL_DOCUMENT_REVIEW_BASE_URL`。
- 关联任务: T-029、T-032
- 备注: 第一版不接入 FastGPT 原工作流中的内网 `detect` 服务，不处理扫描 PDF OCR，也不生成带批注的 Word 修订稿；报告不替代单位公文审核流程。OpenAI-compatible 入口用于 FastGPT/Dify LLM 节点流式输出，可从 prompt 的“公文文件”区块、平台 `附件：` 列表或 OpenAI content parts 的 `file_url.url` 读取服务端路径或文件链接。

### contract-review

- 状态: Ready
- 用途: 基于 FastGPT 导出工作流“合同审查大师”的有效经验创建的合同六维审查智能体，按委托方角色、合同类型和交易背景审查合同，输出风险清单、评分评级和整改建议。
- 源码路径: `src/agents/contract_review/`
- 运行入口: `python -m src.agents.contract_review review <contract> --client-role 甲方 --contract-type 技术服务合同 --transaction-background <背景> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.contract_review.mcp_server`；HTTP `python -m src.agents.contract_review.mcp_server --transport http --host 127.0.0.1 --port 8009 --path /mcp`；tool 名称 `review_contract`。
- API 入口: `uvicorn src.agents.contract_review.api:app --reload --port 8009`，主接口 `POST /review`。
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `contract-review-agent`。
- 调试方式: 先用内置 `src/agents/contract_review/examples/示例服务合同.md` 执行 `--dry-run`，确认解析、分块、六维审查结构和评分口径；正式运行再接入 DeepSeek 或 DashScope/Qwen。
- 需要的环境变量: 默认 `GPU_STACK_API_KEY`，旧 `DEEPSEEK_API_KEY` 仅兼容回退；DashScope provider 使用 `DASHSCOPE_API_KEY`。可选 `CONTRACT_REVIEW_MODEL`、`CONTRACT_REVIEW_BASE_URL`。
- 关联任务: T-028、T-032
- 备注: 第一版支持 DOCX、文本型 PDF、TXT、MD；扫描 PDF OCR、外部法律知识库检索、红线批注和合同全文改写暂不包含。报告必须声明不替代执业律师正式法律意见。OpenAI-compatible 入口用于 FastGPT/Dify LLM 节点流式输出，可从 prompt 的“合同文件”区块、平台 `附件：` 列表或 OpenAI content parts 的 `file_url.url` 读取服务端路径或文件链接。

### langchain-knowledge-base

- 状态: Ready
- 用途: 基于工作区级可复用知识库核心的 RAG 智能体，支持 PDF、DOCX、Markdown、TXT 文档入库、检索问答、来源引用和无依据拒答。
- 源码路径: `src/agents/langchain_knowledge_base/`
- 核心路径: `src/knowledge_base/`；公共接口为 `KnowledgeBaseManager(namespace)` 的 `ingest`、`retrieve`、`answer` 和 `list_knowledge_bases`。
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `langchain-knowledge-base-agent`。
- 内部管理接口: `GET /v1/knowledge-bases`、`POST /v1/knowledge-bases/{name}/ingest`、`POST /v1/knowledge-bases/{name}/retrieval`，不由网关公开。
- 数据隔离: `data/knowledge_bases/<agent-namespace>/<knowledge-base-name>/`；当前 namespace 为 `langchain-knowledge-base-agent`，默认知识库为 `default`。
- 需要的环境变量: 默认复用 `GPU_STACK_API_KEY`/`GPU_STACK_BASE_URL`；问答模型 `deepseek-v4-flash`，嵌入模型 `qwen3-vl-embedding-8b`。可用对应 `KB_*` 变量覆盖。
- 关联任务: T-027、T-035、T-036
- 备注: 旧 `kb_api`、Langflow、primary/secondary 配置及旧 Chroma 数据已破坏性移除，不提供迁移；新智能体可直接复用核心并使用独立 namespace。

### batch-resume-review-llm

- 状态: Ready
- 用途: 批量简历唯一业务实现，同时作为 Dify/FastGPT 自定义 OpenAI-compatible LLM 模型，输出审查进度和最终报告。
- 源码路径: `src/agents/batch_resume_review_llm/`
- 运行入口: `python -m src.agents.batch_resume_review_llm review <resume-a> <resume-b> --job-description <jd.txt> --output <report.md>`
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `batch-resume-review-agent`。
- MCP 入口: stdio `python -m src.agents.batch_resume_review_llm.mcp_server`；HTTP `python -m src.agents.batch_resume_review_llm.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp`；tool 名称 `review_resumes`。
- API 入口: `uvicorn src.agents.batch_resume_review_llm.api:app --reload --port 8006`，主接口 `POST /review`。
- 调试方式: 先用 `/v1/chat/completions` 的 `dry_run=true` 验证 Dify/FastGPT 模型接入和流式输出，再接入正式模型。
- 需要的环境变量: `GPU_STACK_API_KEY`、`GPU_STACK_BASE_URL`；扫描件 OCR 另用 `DASHSCOPE_API_KEY`。
- 关联任务: T-024
- 备注: OpenAI-compatible 入口可从“简历文件”区块、平台 `附件：` 列表或 OpenAI content parts 的 `file_url.url` / `image_url.url` 读取文件链接；旧包名不再提供。

### resume-review

- 状态: Ready
- 用途: 审查人力部门收到的 DOCX、文本型 PDF 和 TXT 简历，输出基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配评分和面试追问建议。
- 源码路径: `src/agents/resume_review/`
- 运行入口: `python -m src.agents.resume_review review <resume> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.resume_review.mcp_server`；HTTP `python -m src.agents.resume_review.mcp_server --transport http --host 127.0.0.1 --port 8003 --path /mcp`；tool 名称 `review_resume`。
- API 入口: 单独调试可运行 `uvicorn src.agents.resume_review.api:app --reload --port <非8008端口>`，主接口 `POST /review`；`8008` 已由统一网关占用。
- 调试方式: 先运行 `--dry-run` 验证简历解析、分块和 JD 输入，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: 默认 `GPU_STACK_API_KEY`，旧 `DEEPSEEK_API_KEY` 仅兼容回退；DashScope provider 使用 `DASHSCOPE_API_KEY`。可选 `RESUME_REVIEW_MODEL`、`RESUME_REVIEW_BASE_URL`。
- 关联任务: T-015
- 备注: 第一版支持文本型 PDF，不支持扫描件 OCR；岗位 JD 可选，未提供 JD 时不生成匹配分，避免伪造岗位匹配依据。审查事项按 Markdown 文件拆分，正式 LLM 审查按基本条件/筛选条件/专业条件三个维度并行调用后汇总；学历维度默认加载 `src/reference_data/universities/` 高校参照。

### tender-format-review

- 状态: Ready
- 用途: 审查大型中文招标文件 `.docx` 的格式、章节、表格和跨章节一致性问题，输出 Markdown 审查报告。
- 源码路径: `src/agents/tender_format_review/`
- 运行入口: `python -m src.agents.tender_format_review review <docx> --review-guide <md> --catalog <txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.tender_format_review.mcp_server`；HTTP `python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp`；tool 名称 `review_tender_format`。
- API 入口: `uvicorn src.agents.tender_format_review.api:app --reload --port 8001`，主接口 `POST /review`。
- OpenAI-compatible 入口: 统一网关 `http://<host>:8008/v1`，模型 ID `tender-format-review-agent`。
- 调试方式: 先运行 `--dry-run` 验证 docx 解析、分块和输出路径，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: 默认 `GPU_STACK_API_KEY`，旧 `DEEPSEEK_API_KEY` 仅兼容回退；DashScope provider 使用 `DASHSCOPE_API_KEY`。可选 `TENDER_REVIEW_MODEL`、`TENDER_REVIEW_BASE_URL`、`TENDER_REVIEW_MAX_REMOTE_FILE_BYTES`、`TENDER_REVIEW_REMOTE_TIMEOUT_SECONDS`。
- 关联任务: T-009、T-011、T-012、T-026
- 备注: 对 10 万字以上文件默认采用“解析元素 -> 章节/长度分块 -> 分块审查 -> 汇总复核”，不依赖整篇一次放入上下文。OpenAI-compatible 入口用于 Dify/FastGPT LLM 节点流式输出，可从 prompt 的“招标文件”区块、平台 `附件：` 列表或 OpenAI content parts 的 `file_url.url` 读取服务端路径或 HTTP(S) `.docx` 链接。Codex 后台起常驻 HTTP MCP 时，优先直接调用 `C:\Users\Lenovo\.conda\envs\langchain\python.exe`，不要依赖 `conda run`；详见 `docs/development/RUN_AND_DEBUG.md` 和 `docs/operations/PROBLEM_LOG.md` 的 2026-06-17 记录。

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

