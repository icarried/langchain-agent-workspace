# Decisions

用于记录对后续开发有影响的设计决策。

## 2026-07-30 - 三线表使用重复表头和整行换页

- 状态: Accepted
- 决策: 三线表保留 1.5 pt 顶线、0.75 pt 表头下线和 1.5 pt 底线，关闭左右边框、
  内横线和竖线。首行写入 OOXML `tblHeader`，所有行写入 `cantSplit`。
- 原因: `公文格式化.md` 只要求经典三线结构；截图中的灰色虚线是 Word/WPS 编辑网格线，
  不能保存为真实边框。跨页表格需要由 Word/WPS 重复首行，手工复制表头会改变表格内容并
  难以随分页变化自动调整。
- 影响: 表格跨页时客户端自动显示相同表头，并尽量把单条记录保留在同一页；实际分页仍受
  字体和客户端渲染影响，没有渲染器时只能静态确认 OOXML 属性已写入。

## 2026-07-30 - 附件标签和清单使用独立段落

- 状态: Accepted
- 决策: 附件说明采用截图所示的独立段落结构：`附件：` 首行缩进 2 个中文字符，附件
  项目从下一段开始并整体左缩进 2 个中文字符，长项目换行与序号对齐。
- 决策: 输入中的 `附件：首项` 允许确定性拆段，附件项目行首的半角空格、全角空格和制表符
  视为旧布局字符并清理。内容保护使用附件语义快照验证名称和顺序，同时继续逐项保护其他
  正文、表格和规范化后的输出。
- 原因: 旧的“标签与首项同段、附件名称悬挂对齐”与用户给出的实际公文版式不一致，且保留
  手工空格再叠加段落缩进会造成附件项目横向错位。
- 影响: 格式化前后段落数量可能因附件首项拆分增加，但附件名称、顺序和其他业务内容不变；
  金标准和平台回归必须覆盖中文、英文冒号两种输入。

## 2026-07-30 - 公文规范正文优先并分层报告合规状态

- 状态: Accepted
- 决策: `临时文件/公文格式化配置/公文格式规范.docx` 的正文要求是格式化规则的权威
  来源。样例文件内部属性与正文冲突时采用正文值，当前右边距为 `2.6 cm`，行网格为
  `560 twips`。规则集中在标准参数、段落角色、页面版式、附件版记和合规校验模块中。
- 决策: 报告区分自动格式化、静态校验和渲染复核。OOXML 属性及内容不变可以静态验证；
  实际 28 字 × 22 行、标题回行、表格跨页、印章位置和版记偶数页必须经过 Word/WPS 或
  LibreOffice 全页渲染，没有渲染结果时标记为 `verified=false`。
- 原因: DOCX 内部网格和段落属性只能表达排版意图，不能证明特定客户端、字体和打印机下的
  最终分页。把未渲染规则报告为通过会产生错误的合规结论。
- 影响: `message.file` / `delta.file` 文件协议不变，报告增加未验证摘要；调用方可以交付
  格式化文件，但必须保留视觉复核提示。规范或版式要求变化时先更新标准矩阵和金标准测试。

## 2026-07-30 - 公文格式化采用 DOCX 原位规则处理和内容不变校验

- 状态: Accepted
- 决策: 第一期不复刻 Markdown/Pandoc 中转，也不引入 LLM。智能体在原始 DOCX 上按
  段落文本和位置确定角色，由 `python-docx` 写入格式，并在发布前比较正文段落和表格
  单元格内容快照。
- 原因: 当前目标是只格式化；DOCX 往返 Markdown 会增加表格、图片、分节等结构损失风险，
  LLM 也不是 `SKILL.md` 所列规则的必要条件。
- 影响: 无法确定的复杂段落暂按正文处理；未来如引入 LLM，只允许返回段落角色标签，不能
  返回或重写正文。日期、重复段落和空段落均不再自动删除。

## 2026-07-30 - 公文格式化字体由用户端提供

- 状态: Accepted
- 决策: 公文格式化服务只在 DOCX OOXML 中写入目标字体名称，不打包字体文件，不安装
  `fontconfig`，也不执行字体探测或返回字体健康状态。
- 原因: `python-docx` 修改文档格式时不渲染字形；只有打开文件的 Word/WPS 客户端或未来的
  服务端 PDF/图片渲染组件需要实际字体。
- 影响: 智能体镜像和健康检查更简单；用户端需安装公司规定字体。未来增加服务端渲染时，
  字体应作为渲染服务的独立依赖重新评估。

## 2026-07-30 - 部门知识库使用版本化快照原子发布和可见进度

- 状态: Accepted
- 决策: 多文档保存先幂等归档 MinIO 原件，再在
  `versions/<version-id>/` 构建完整文档快照、Chroma 和 manifest；校验索引条目数后，
  仅以原子替换根 manifest 的 `active_version` 发布新版本。
- 决策: SSE 在后台线程执行保存，通过事件队列逐文件报告下载、归档、解析、OCR、
  嵌入和提交状态，长步骤定期发送心跳；服务端日志记录请求 ID、失败阶段和已移除
  URL 查询签名的 traceback。
- 原因: 旧实现先写 live documents、重置当前 Chroma，长时间没有 SSE 事件；扫描件
  或多文档失败会同时造成平台超时感知和“原件存在但索引不可用”的半完成状态。
- 影响: 只有 `active_version` 更新后才能向用户声明“保存并完成索引”；失败保持旧
  快照可检索。默认保留当前和上一版索引，MinIO 历史原件仍独立保留。

## 2026-07-30 - 部门知识库采用多查询检索和仅随来源提供下载

- 状态: Accepted
- 决策: `query` 意图先由 DeepSeek 输出最多 5 个结构化检索查询，始终保留原问题；
  改写失败时退回原问题。多个查询批量向量检索后按 chunk 去重并使用 RRF 融合，再把
  最多 20 个 chunk、10 个文档的证据交给 DeepSeek回答。第一版不接入尚未验证调用
  契约的独立 reranker。
- 决策: chunk ID和索引保留在内部证据中，用户“来源”只显示去重后的文档名。文件
  下载不是独立意图，也不解析上一轮回答；本次检索命中的当前活动原件直接通过既有
  `delta.file` 发送，由平台安全校验后写入现有 `file_mapping` 并展示下载控件。
- 原因: 原始单查询检索难以覆盖复合问题、同义词和上下位概念，而 `#chunk-N` 对普通
  用户没有业务含义。把下载绑定到服务端实际检索证据，比按文件名或解析历史回答更
  直接，也不会产生错误的跨轮文件关联。
- 影响: 问答增加一次可降级的 DeepSeek改写调用；服务端必须从结构化 citations 和活动
  文档目录生成来源及文件载荷，不能从模型文本反向解析。保存、列表、任务状态和帮助
  响应不附带下载文件。

## 2026-07-30 - 部门知识库普通保存使用增量原子索引

- 状态: Accepted
- 决策: 普通新增或替换文档时复制当前不可变 Chroma快照，按 `source` 删除本批实际
  变化文档的旧 chunk，仅解析和嵌入这些文档，再校验新索引计数并原子切换 manifest。
  首次建库、显式 rebuild或 embedding签名变化仍执行全量重建。
- 原因: 用户提供的 `thinking.txt` 显示一次上传 20 份新文件却重新解析了活动目录全部
  449 份文档并生成 3070 个向量。该放大效应会让 100 文件任务更容易超时，也浪费
  OCR和 embedding资源。
- 影响: 未变化历史文档不再重复解析、OCR或嵌入；活动索引在复制期间保持只读，构建
  失败仍使用旧 manifest。同名同内容可直接幂等，同名新内容只替换该来源的 chunk。

## 2026-07-29 - 公文格式化使用冻结规则内核并由 AI 平台持久化成品

- 状态: Accepted
- 决策: 新建 `official-document-formatting-agent`，直接调用公司已经验证的
  `format_docx` 规则，不引入 LLM 分类、润色或改写；格式化结果通过结构化
  `message.file` / `delta.file` 返回。
- 决策: Agent 不持有 AI 平台 MinIO 凭证。AI 平台解码文件后使用统一 DOCX 验证器、
  `GeneratedArtifactService` 和现有 `file_mapping` 完成用户归属与下载。
- 原因: 排版规则已经完成公司验收，继续让模型参与会引入不确定性；文件持久化属于平台
  已有的权限与资产边界，不应在 worker 中重复实现。
- 影响: 智能体只写入 DOCX 字体名称，不在服务端安装或探测公文字体；字体由打开文件的
  用户端提供。平台消费 `delta.file` 并产生通用 `file_delta`。

## 2026-07-29 - 生成视频由 AI 平台持久化后再向用户公开

- 状态: Accepted
- 决策: 视频 Agent 把 ComfyUI 输出地址作为结构化 `video.source_url` 交给 AI 平台，
  不再把该内网地址写入用户可见 Markdown；AI 平台后端负责下载、校验并写入自己的
  MinIO和 `file_mapping`，最终只向浏览器返回平台资产 URL。
- 原因: ComfyUI `10.180.26.16:8188` 属于生成网络，不保证平台用户可达；容器或宿主机
  临时文件也不具备用户归属、持久化和统一权限控制。
- 影响: AI 平台需增加视频产物处理和 `video_delta`；下载来源必须使用主机/CIDR白名单、
  大小和超时限制。Agent暂时保留 `video.content_url` 作为旧客户端兼容字段。

## 2026-07-28 - 部门及公司规定知识库使用固定空间参数和项目专属 MinIO

- 决策: 新增 `department-knowledge-base-agent`，同一 OpenAI-compatible模型通过请求
  顶层 `knowledge_id` 选择八个固定部门空间及独立的“公司规定”空间；字段只接受服务端白名单，不从用户文字
  推导，未知或缺少值直接拒绝。
- 决策: Qwen3.5只识别 `save/query/list/help/unknown` 意图；附件存在不等于保存，
  删除、跨部门访问和权限变更不由 LLM执行。
- 决策: `ai-app-platform` MinIO仅作为上传入口。保存时原件复制到本项目专属 MinIO，
  每部门一个 bucket；本地知识库卷保留解析快照和 Chroma。MinIO 9000/9001只在
  Compose内部开放，不发布宿主机端口。
- 决策: OCR通过共享 provider接口逐页调用 GPU Stack `paddleocr-vl-1.6`。当前属于
  VLM逐页 Markdown提取，不声称等同官方完整布局分析流水线；后续可替换 provider。
- 原因: 避免平台和知识库项目在原件生命周期、凭证、备份及故障域上耦合，同时保持
  一个接口、一个模型 ID和明确的数据边界。
- 影响: 生产必须分别备份 `knowledge_base_data` 和 `department_kb_minio_data`，
  配置独立 MinIO凭证；离线发布包还必须包含固定版本 MinIO镜像。

## 2026-07-27 - 服务器发布使用不可变镜像与离线校验包

- 决策: 机器人管理平台服务器部署使用不可变镜像标签、gzip 压缩的 Docker save
  发布包和 SHA-256 校验；远端只导入镜像并以 `--no-build --pull never` 启动。
- 决策: 服务器宿主端口为 `10085`，容器网关仍监听 `8008`。Compose 通过
  `AGENT_GATEWAY_PORT` 和 `AGENT_WORKSPACE_IMAGE` 分别配置发布端口和镜像版本。
- 决策: 首次部署不迁移本机知识库卷，服务器创建自己的空
  `agent-workspace_knowledge_base_data` 卷；升级和回滚不得使用 `down -v`。
- 原因: 目标服务器与本机构架同为 amd64，但服务器可能不适合在线重建；不可变标签和
  校验包能确保发布可追溯、可断点续传和可回滚。
- 影响: 每次服务器发布应保留 release 目录、上一版镜像和生产 `.env.local`；本机
  `local-proxy` profile 与 MinIO 传输映射不得复制到服务器。

## 2026-07-24 - GPU Stack统一模型与对话式图片生成

- 决策: 工作区默认模型调用统一迁移到 `http://10.100.5.33:8003/v1`，使用 `GPU_STACK_API_KEY`。现有 DeepSeek智能体继续使用 `deepseek-v4-flash`，知识库嵌入改为 `qwen3-vl-embedding-8b`。
- 决策: 新增 `image-generation-agent`。Qwen3.5视觉模型负责提示词改写，`qwen-image` 负责文生图，`qwen-image-edit` 负责单图编辑；当前用户图片优先，否则沿用最近助手图片。
- 决策: 图片结果通过 Chat Completions多模态 content数组返回，worker 不持久化。AI 应用平台负责写入 MinIO并通过助手附件形成连续编辑闭环。
- 决策: `7897` 代理仅属于当前开发机。本机未提交的 `.env` 启用 `local-proxy` Compose profile和 host-network sidecar；服务器默认不启用 profile、不设置容器代理，直接访问 GPU Stack。
- 影响: 嵌入签名变化要求显式重建已有知识库；平台未完成图片输出 handoff前只能获得协议级图片结果。

## 2026-07-27 - 图片流式 thinking只公开执行进度

- 决策: 图片智能体把 LangGraph节点完成事件、最终改写提示词和生成心跳放入 `delta.reasoning_content`；不流式输出 Qwen3.5隐藏推理链。
- 原因: 平台需要在图片生成完成前立即获得反馈，同时不能把内部思维链当成产品接口。
- 影响: `thinking=true` 时前端可展示逐阶段状态；`thinking=false` 时相同进度走字符串 `delta.content`。最终图片协议保持为单次多模态 `delta.content` 数组。

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
- 影响: 新入口提供 `GET /v1/models` 和 `POST /v1/chat/completions`，模型 ID 为 `tender-format-review-agent`。prompt 通过“招标文件”区块传入服务端 `.docx` 路径或 HTTP(S) `.docx` 链接；远程文件临时下载后交给原服务层，报告仍由原 LangGraph 工作流生成。流式模式默认把非最终进度写入 `delta.reasoning_content`，最终报告写入 `delta.content`，可用 `thinking=false` 回退。为兼容当前 FastGPT/MinIO 部署，临时将 `10.71.2.94:9000` 的实际传输地址映射为 `127.0.0.1:9002`，同时保留原始 `Host` 头；修正 FastGPT 签名地址后应删除该映射。

## 2026-07-13 - 知识库智能体纳入工作区统一追踪

- 决策: 移除 `src/agents/langchain_knowledge_base/.git` 嵌套仓库元数据，使知识库智能体与其他智能体一起由工作区根 Git 仓库追踪；保留其 `pyproject.toml`、`.env.example`、Dockerfile、Compose 和本地运行入口。
- 原因: 用户需要创建一个整体 GitHub 仓库并统一追踪提交，嵌套 Git 仓库会让根仓库无法直接纳入知识库源代码及其后续修改。
- 影响: 该智能体的源码、测试、文档和运行配置随主仓库提交；运行、测试、入库和 Docker Compose 都从工作区根目录执行。应用配置会按自身目录解析 `.env`、文档和 Chroma 数据，避免根目录启动改变运行数据位置。Chroma 继续使用本地 `PersistentClient`，Compose 使用 `kb_chroma_data` 卷，默认不启动独立 Chroma 服务。

## 2026-07-07 - FastGPT 工作流转化优先抽取可复用经验

- 决策: 首个 FastGPT JSON 转化对象选择 `合同审查大师(1).json`，落地为 `contract-review`。实现保留“表单上下文、六维审查、评分评级、整改建议”的设计经验，但不照搬 FastGPT 的节点 ID、平台 OCR 子应用或顺序编排。
- 原因: 合同审查主题边界清晰，能复用工作区已有 LangGraph 分块审查模式；相比电厂问数工作流，它不依赖未知数据库 schema；相比简历/RAG 工作流，它不会与已有智能体重复。
- 影响: 后续转化 FastGPT 工作流时应先判断哪些节点体现了业务经验，哪些只是平台编排细节。工作区智能体优先沉淀确定性解析、分块、dry-run、CLI/API/MCP 和测试，而不是逐节点复制。

## 2026-07-07 - 公文优化转化为本地确定性检查加报告整理

- 决策: `公文优化.json` 转化为 `official-document-review`，保留“上传文件 -> 检测 -> 美化输出”的经验，但不直接依赖原工作流中的 `http://172.16.1.24:30019/detect` 内网服务。
- 原因: 内网检测服务不可保证在本工作区可达；把第一版做成本地 DOCX/TXT/MD/PDF 解析和确定性检查，可测试、可离线 dry-run，后续若检测服务稳定再作为可选工具接入。
- 影响: 第一版只做 GB/T 9704-2012 基础结构与版式线索检查，不声称完整替代人工公文审核或单位模板审核。

## 2026-07-07 - 智能简历筛选保留结构化评分口径而非复制长提示词

- 决策: `智能简历筛选(1).json` 转化为 `smart-resume-screening`，重点沉淀岗位参数、硬性条件、优先条件、淘汰条件、量化评分和排行榜输出；实现上采用确定性初筛评分加可选模型报告整理。
- 原因: 工作区已有更完整的 `batch-resume-review`，不宜重复实现 OCR、远程 URL 和复杂招聘规则；这个 FastGPT 工作流的价值在于结构化筛选配置和快速排行榜。
- 影响: 后续简历场景按复杂度选型：快速岗位条件筛选用 `smart-resume-screening`，完整批量审查和交付包装用 `batch-resume-review`。

## 2026-07-07 - 智能简历结构化初筛增加 OpenAI-compatible 薄包装

- 决策: 在 `smart-resume-screening` 内新增 `openai_compatible_api.py`，模型 ID 为 `smart-resume-screening-agent`，复用原 `screen_resumes` 服务层解析岗位要求、简历路径、打分和生成报告。
- 原因: FastGPT/Dify 的 LLM 节点更适合流式展示筛选进度和最终报告；薄包装能避免业务逻辑分叉，也保持该智能体的轻量定位。
- 影响: 该入口适合服务端本地路径或平台已能传递的文件路径；远程 MinIO URL、OCR、多格式复杂解析仍优先使用 `batch-resume-review-llm`。

## 2026-07-07 - 合同审查与公文格式检查补齐 OpenAI-compatible 入口

- 决策: 为 `contract-review` 和 `official-document-review` 分别新增 `openai_compatible_api.py`，模型 ID 分别为 `contract-review-agent` 和 `official-document-review-agent`，均复用原服务层。
- 原因: 用户希望近期从 FastGPT JSON 转化出的智能体都能作为 FastGPT/Dify 自定义 LLM 节点调用；薄包装可以统一模型探测、流式输出和平台接入方式。
- 影响: 两个入口均支持 readiness、非流式、流式 SSE 和 `thinking=false`；文件读取仍由原智能体服务层负责，复杂远程文件下载和 OCR 后续按实际平台需要单独扩展。

## 2026-07-07 - 文件型 OpenAI-compatible 入口共享附件解析

- 决策: 新增 `src/agents/openai_compatible_inputs.py`，统一解析 OpenAI-compatible 消息中的文本、平台 `附件：` 列表、JSON 数组、多行 URL、本地路径和 content parts 的 `file_url.url` / `image_url.url`。
- 原因: FastGPT/Dify 等平台上传文件后不一定会渲染为各智能体原先要求的“简历文件/合同文件/公文文件/招标文件”区块；把兼容逻辑放在薄适配层能避免要求平台硬编码业务标签，也避免 5 个入口继续复制分叉。
- 影响: `batch-resume-review-llm`、`smart-resume-screening`、`contract-review`、`official-document-review` 和 `tender-format-review` 的 OpenAI-compatible 入口都能读取 `附件：` 或 content parts 文件 URL；原 CLI/API/MCP 和服务层不变。URL 仍必须能被智能体服务所在网络环境访问。

## 2026-07-07 - 简历类 LLM 入口支持附件前正文作为 JD

- 决策: `batch-resume-review-llm` 和 `smart-resume-screening` 在已识别简历文件但没有显式 `岗位要求` / `JD` 区块时，把首个 `附件`、`简历文件`、`简历路径` 或 `输出要求` 之前的正文作为岗位要求，并保留 Markdown 原文。
- 原因: 平台聊天页上传文件后会把附件 URL 追加到用户正文之后；用户常直接粘贴 Markdown 岗位要求，而不是额外加 `岗位要求：` 标签。旧解析会误判为“有附件但没有 JD”，返回 readiness。
- 影响: 简历类 OpenAI-compatible 入口对平台真实输入更宽容；显式标签协议仍优先。合同、公文和招标入口不依赖 JD 才能启动，因此不需要同类 fallback。

## 2026-07-14 - 统一网关路由到隔离 worker

- 决策: OpenAI-compatible 生产入口统一为 `8008`，网关按 `model` 路由到独立 worker；worker 在 Compose 内统一监听 `8080`，不发布宿主机端口。本机开发使用同一注册表和子进程监管器。
- 原因: 每个智能体占用独立对外端口不利于扩容，也使平台配置和故障处理分散。网关与 worker 分进程/容器可在保持单入口的同时隔离故障。
- 影响: FastGPT/Dify 统一配置 `http://<host>:8008/v1`；`GET /v1/models` 只返回健康模型。原独立 OpenAI 端口及 REST/MCP 源码仅用于调试，不进入生产 Compose。此决策覆盖此前将 `8008` 分配给 `resume-review` REST API 的约定。

## 2026-07-14 - 批量简历业务实现收敛到 LLM 包

- 决策: `batch_resume_review_llm` 是批量简历唯一业务实现；`batch_resume_review` 旧包及只覆盖该旧包的测试均已移除。
- 原因: 两套复制代码、示例和参考资料会持续分叉，统一网关已经通过进程隔离解决生产稳定性问题，不再需要源码复制隔离。
- 影响: 模型 ID 和现有平台调用行为保持不变；新增功能、修复、资料和测试只维护在 canonical 包。旧 CLI/REST/MCP包路径不再兼容。此决策取代 2026-06-25 的“隔离复制”决策。

## 2026-07-14 - 知识库按 namespace 和名称破坏性重构

- 决策: 删除旧 `kb_api` 独立项目、Langflow、primary/secondary 路由和旧 Chroma 兼容，建立工作区级 `KnowledgeBaseManager(namespace)`；数据固定存放于 `data/knowledge_bases/<namespace>/<name>/`。
- 原因: 旧结构围绕单个智能体和两个硬编码知识库设计，难以让后续多个智能体可靠复用并隔离数据与 embedding 配置。
- 影响: 不迁移测试数据或旧向量库。每个智能体使用稳定安全 slug namespace，每个知识库独占 documents、Chroma 和 manifest；embedding 配置变化要求显式重建。

## 2026-07-14 - 文件型智能体共享安全远程附件传输

- 决策: 文件型 OpenAI-compatible 包装器共用远程附件模块，统一主机白名单、大小、超时、扩展名、临时文件清理及签名 Host 传输映射。
- 原因: 各智能体自行下载会重复安全边界，并产生针对单台机器的硬编码端口映射。
- 影响: 招标智能体移除 `10.71.2.94:9000 -> 127.0.0.1:9002` 硬编码；特殊网络使用 `AGENT_REMOTE_TRANSPORT_OVERRIDES` 显式配置，保留原始 Host 与查询签名。

## 2026-07-28 - 视频生成 worker 直接调用 ComfyUI

- 状态: Accepted
- 决策: 新建 `comfyui-video-generation-agent`，在 worker 内完成 LTX 2.3 工作流渲染、ComfyUI提交和状态轮询，不再依赖单独部署的 Videos API；统一网关仍是唯一公开的 OpenAI-compatible 入口。
- 原因: 现有 Agent 经 Videos API 二次转发会增加一个进程、部署单元和故障点，而工作区 worker 已能承担受控工具调用和异步进度管理。
- 正面影响: 部署链路缩短为“gateway -> worker -> ComfyUI”；工作流参数白名单、SSE进度、dry-run和错误脱敏集中在 Agent包内。
- 负面影响: 首版不提供独立持久化任务数据库；worker重启后不能通过自身恢复旧任务状态。最终下载 URL直接指向 ComfyUI，因此调用方必须能访问其 public base URL。
- 失败模式与缓解: ComfyUI不可用时 worker健康检查返回503并从网关模型列表隐藏，不阻塞其他 Agent；提交校验失败时返回长度受限的节点错误；长任务受服务端最大等待时间限制，超时不取消ComfyUI任务。
- 替代方案: 保留独立 Videos API（部署复杂度较高）；把视频逻辑放入 gateway（破坏路由层职责和故障隔离）；把视频 Base64塞入 Chat Completion（大文件内存与平台兼容风险过高）。
## 2026-07-30 - 部门知识库采用结构化附件原名并保留旧入口

- 决策: 共享 OpenAI-compatible 输入层新增内部 `AttachmentReference`，保留附件 URL、
  原始文件名、MIME 和来源方式；部门知识库优先消费 `file_url.filename`，同时继续
  接受旧字符串 `files`、正文 URL、`附件：` 文本和既有 content parts。
- 原因: AI 应用平台已用 PG `file_mapping.file_id` 保存可信原名和对象位置，并可在
  转发前重新签发 URL；URL末段是对象存储名称，不能承担业务文件名语义。
- 影响: 平台附件模式可使用 `file_url_content_part`。知识库仅把 URL用于本次下载，
  不保存其查询签名；快照、manifest和归档对象使用校验后的原始文件名。
- 存储边界: 平台 MinIO仍是上传传输源，知识库 MinIO仍保存长期原件，不合并两个
  MinIO，也不在知识库目录中长期引用平台预签名 URL。
