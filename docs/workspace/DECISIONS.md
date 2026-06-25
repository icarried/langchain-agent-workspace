# Decisions

用于记录对后续开发有影响的设计决策。

## 2026-06-16 - 使用轻量 Agent 工作空间结构

- 决策: 先建立 `AGENTS.md`、`.agents/tasks/`、`docs/`、`src/`、`tests/` 和 `secrets/`。
- 原因: 当前工作空间很干净，先建立清晰框架，避免过早引入复杂工程结构。
- 影响: 后续 Agent 可以通过固定入口快速理解任务、环境、密钥和问题记录。

## 2026-06-16 - 使用 `.env.local` 管理本地真实密钥

- 决策: 原始 key 归档到 `secrets/raw/unorganized-api-keys/`，开发读取根目录 `.env.local`。
- 原因: `.env.local` 易被 `python-dotenv` 加载，且已被 `.gitignore` 忽略。
- 影响: 文档和模板只记录变量名，不记录真实值。

## 2026-06-16 - 将工作空间定位为多智能体开发空间

- 决策: 本工作空间用于承载多个 LangChain / LangGraph 智能体，并用 `docs/workspace/AGENT_REGISTRY.md` 登记每个智能体。
- 原因: 用户计划在同一工作空间创建多个智能体，需要统一入口、状态、源码路径和调试说明。
- 影响: 新增智能体时应同步更新登记表、任务板和运行调试文档。

## 2026-06-16 - 确认 `langchain` conda 环境已创建

- 决策: 后续开发默认使用用户已创建的 conda 环境 `langchain`。
- 原因: 环境已经就绪，不需要 Agent 再执行环境创建步骤。
- 影响: 文档中的默认运行命令为 `conda activate langchain`。

## 2026-06-16 - 招标文件审查采用分块 LangGraph 工作流

- 决策: `tender-format-review` 智能体不把 10 万字以上招标文件整篇一次提交给模型，而是先解析 docx 元素，再按章节和长度分块，最后汇总分块审查结果。
- 原因: DeepSeek、Qwen 等模型上下文上限会随具体模型版本变化；即使长上下文可容纳全文，分块仍更利于证据定位、跨章节复核、失败重试和成本控制。
- 影响: 审查 prompt 必须要求证据位置和“需跨章节复核”标记，汇总节点负责去重和列出未解决复核项。

## 2026-06-16 - 将 LangChain 智能体创建经验沉淀为 workspace skill

- 决策: 新增 `.codex/skills/langchain-agent-builder/`，用于指导后续在本工作空间创建 LangChain / LangGraph 智能体。
- 原因: 用户计划持续创建多个智能体，需要把任务登记、目录结构、provider 配置、长文档分块、dry-run 和验证流程固定下来。
- 影响: 后续创建新智能体时可显式使用 `$langchain-agent-builder`。

## 2026-06-22 - 区分简历审查测试夹具与 MCP 输入协议

- 决策: `resume-review/examples/` 使用 Markdown 保存可读测试样例；MCP 只接收 DOCX、文本型 PDF、TXT 简历的 base64 内容和岗位要求普通文本。
- 原因: Markdown 便于维护测试数据，但不代表招聘系统实际传输格式，也不应成为 MCP 调用方的额外约束。
- 影响: 本地 loader/CLI 可读取 Markdown 测试夹具；MCP 上传 Markdown 会明确返回不支持的文件类型错误。

## 2026-06-22 - 批量简历先筛除再排序

- 决策: `batch-resume-review` 采用候选人独立审查、硬条件决策、确定性分组和排序；`excluded` 不参与排名，`pending_review` 的最终口径由后续“简历筛除与人工复核使用正交口径”决策修订。
- 原因: 防止高匹配分掩盖明确硬条件缺口，也避免因信息不足而武断筛除；确定性排序还能避免并行模型返回顺序影响名次。
- 影响: 审查规则合并为一个 Markdown 统一定义筛除门槛和量表；候选人级模型输出经过解析层复核，`not_met` 会覆盖模型给出的高分。

## 2026-06-22 - 高校名单区分固定历史快照与动态查询

- 决策: 985/211 保存教育部固定历史名单；双一流按轮次和年份保存；“一本”按省份和招生年份核验；世界排名只使用带版次和访问日期的官方来源或合法快照。
- 原因: 985/211 不再新增，而双一流、招生批次和世界排名会变化；把它们混成一张无年份静态表会直接造成招聘误判。
- 影响: 两个简历智能体默认加载 `src/reference_data/universities/`；缺少动态榜单快照时只输出待核验，不得凭模型记忆生成排名。

## 2026-06-22 - 简历筛除与人工复核使用正交口径

- 决策: 提示词注入和明确硬条件不符者筛除；待人工复核不再是与排名并列的互斥状态，而是排名候选人的附加标记。技能熟练度只参与评分。
- 原因: 证据不足不等于条件不满足，若把待确认候选人排除在排名外，会误伤未在简历中堆砌关键词但实际能力较强的人。
- 影响: `pending_review` 有有效分数时参与排名并同时出现在附加复核项；筛除名单始终无分数且不参与排名。候选人姓名由简历原文提取并与文件名同时展示。

## 2026-06-23 - 独立智能体内置运行依赖和参考资料

- 决策: 可交付的智能体不得依赖多智能体工作区的其他 Python 包或共享数据目录；源码、规则、静态参考资料、依赖清单、环境模板和 MCP 示例全部封装在智能体发行包内。
- 原因: 仅复制源码目录会遗漏跨包解析器和高校资料，也会让 MCP 配置依赖原仓库路径，无法可靠交付或版本追溯。
- 影响: `batch-resume-review` 使用包内相对导入和 `references/universities/`；通用打包器读取 `standalone_manifest.json` 生成带 SHA-256 清单的 ZIP，独立包版本与参考资料同步发布。

## 2026-06-24 - 批量简历 API 以内存流读取 MinIO 预签名 URL

- 决策: `resume_paths` 同时接受本地路径和 HTTP(S) URL；远程内容在 loader 内受限读取为内存流，不落盘，再复用既有 DOCX/PDF/文本解析与 LangGraph 工作流。
- 原因: FastGPT Docker Compose 通过 MinIO 预签名 URL 传递文件；在 loader 边界适配可保留单候选人失败隔离，并避免临时文件生命周期侵入服务层。
- 影响: 默认单文件上限 10 MiB、超时 30 秒，可配置主机白名单；URL 查询签名不进入报告、错误或响应路径。API 必须部署在受控内网，生产环境建议明确配置允许的 MinIO 主机。
- 实机补充: 本机 WSL/Docker 的 MinIO 可能只经 Windows localhost 转发可达。仅当 HTTP URL 主机解析为本机地址且首次连接失败时，允许连接回退到同端口的 `127.0.0.1`，同时保留原始 `Host` 头以维持 AWS V4 签名；不对外部主机或 HTTPS 使用该回退。
- 端口映射补充: 当签名 URL 端口与 Docker 发布端口不同，可通过 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT` 指定 localhost 传输地址；该配置不得改变原 URL 或签名 Host。

## 2026-06-24 - 批量简历在 loader 边界按需 OCR

- 决策: `batch-resume-review` 的 CLI、API 和 MCP 统一接受 PDF、DOC、DOCX、MD、TXT；文本优先本地解析，PDF 无文本页面和图片型 DOCX 才调用百炼 `qwen3.5-ocr`。旧 DOC 先禁用宏并转换为 DOCX。
- 原因: 在 loader 边界处理格式和 OCR 可复用现有 LangGraph、单候选人失败隔离及远程 URL 内存流逻辑，同时避免文本型简历产生不必要的 OCR 成本。
- 影响: OCR 复用 `DASHSCOPE_API_KEY`，页面图像会发送给百炼；dry-run 只跳过筛选模型，不跳过解析所必需的 OCR。独立包增加 PyMuPDF，并在 Windows 通过 pywin32 调用 Word，非 Windows 的 DOC 转换可使用 LibreOffice。

## 2026-06-25 - 隔离复制批量简历 OpenAI-compatible 流式适配器

- 决策: 新增 `batch-resume-review-llm`，从 `batch-resume-review` 复制源码、规则和参考资料，再添加 OpenAI-compatible `/v1/chat/completions` 流式入口。
- 原因: Dify/FastGPT 的普通 HTTP 节点不适合长任务轮询；把智能体暴露成自定义 LLM 更容易让平台在对话界面流式显示结果。复制隔离可避免影响原本已能正常运行的批量简历智能体。
- 影响: 新旧两个智能体沿用 API 端口 `8006` 和 MCP 端口 `8005`，但不得同时启动。新智能体优先接收消息中的 JD 文本和简历路径或 MinIO 预签名 URL。

## 2026-06-25 - 招标文件审查增加 OpenAI-compatible LLM 薄包装

- 决策: 在 `tender-format-review` 内新增 `openai_compatible_api.py`，复用原 `review_tender_format` 服务层，不复制智能体目录。
- 原因: 招标文件审查的原 CLI/API/MCP 已稳定，当前只需要让 Dify/FastGPT 的 LLM 节点可以流式接入；薄包装能避免业务逻辑分叉。
- 影响: 新入口提供 `GET /v1/models` 和 `POST /v1/chat/completions`，模型 ID 为 `tender-format-review-agent`。prompt 通过“招标文件”区块传入服务端 `.docx` 路径或 HTTP(S) `.docx` 链接；远程文件临时下载后交给原服务层，报告仍由原 LangGraph 工作流生成。为兼容当前 FastGPT/MinIO 部署，临时将 `10.71.2.94:9000` 的实际传输地址映射为 `127.0.0.1:9002`，同时保留原始 `Host` 头；修正 FastGPT 签名地址后应删除该映射。
