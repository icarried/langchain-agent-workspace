# Task Board

## 使用规则

- 每个任务必须有状态、目标和验收标准。
- 开始前将状态改为 `In Progress`。
- 完成后写清验证方式，再改为 `Done`。
- 被阻塞时写清阻塞原因和下一步需要什么。

## 当前任务

### T-051 公文三线表增加跨页重复表头

- 状态: Done
- 目标: 按 `公文格式化.md` 的三线表规则处理表格，并使表格跨页时自动重复首行表头。
- 验收标准:
  - 表格只保留 1.5 pt 顶线、0.75 pt 表头下线和 1.5 pt 底线，无左右线、竖线和内横线。
  - 第一行写入 Word/WPS 可识别的 `tblHeader`，跨页时自动重复表头。
  - 所有表格行写入 `cantSplit`，避免一条数据行被拆到两页。
  - 采购请示样例重新生成，表格内容保持不变，聚焦回归和静态检查通过。
- 验证:
  - 采购请示三线表为 18 行 6 列，首行 `tblHeader=true`，18 行均具有 `cantSplit`。
  - 表格顶线/底线 `w:sz=12`，表头下线 `w:sz=6`，左右线、内横线和竖线均为 `none`；
    表格内容与原版一致，静态不符合项为 0。
  - 公文格式化、平台文件和网关聚焦回归 27 项通过，Ruff、Python 编译和
    `git diff --check` 通过。
  - 当前环境缺少 LibreOffice，未执行跨页 PNG 渲染；需在 Word/WPS 中确认实际换页位置。
- 最后更新: 2026-07-30

### T-050 公文附件说明改为标签与清单分行

- 状态: Done
- 目标: 按用户提供的版式截图，将 `附件：` 独立成段，并把附件清单从下一行开始按正文
  起点排列。
- 验收标准:
  - `附件：首项` 自动拆为 `附件：` 和首个附件项目两个段落。
  - 标签首行缩进 2 个中文字符，附件项目整体左缩进 2 个中文字符，换行与序号对齐。
  - 只清理附件项目行首的手工空白，附件名称、正文和表格内容不改写。
  - 采购请示样例重新生成，聚焦回归和静态检查通过。
- 验证:
  - 中文和英文冒号输入均能拆分标签与首项；标签 `firstLineChars=200`，所有清单项目
    `leftChars=200` 且无行首手工空白。
  - 采购请示“附件分行测试版”语义内容与原版一致，段落由 22 个增加为 23 个，附件名称
    和顺序不变，静态不符合项为 0。
  - 公文格式化、平台文件和网关聚焦回归 27 项通过，Ruff、Python 编译和
    `git diff --check` 通过。
  - 当前环境缺少 LibreOffice，未执行页面 PNG 渲染；需在 Word/WPS 中复核视觉效果。
- 最后更新: 2026-07-30

### T-049 公文格式规范完整合规改造

- 状态: Done
- 目标: 按 `公文格式规范.docx` 正文要求，将公文格式化从基础字体排版扩展为主体、附件、
  版记、页面网格、奇偶页码和文号的完整确定性处理与校验。
- 验收标准:
  - 实施 `docs/plans/2026-07-30-official-document-formatting-v1.md` 的规则矩阵和任务。
  - 可自动处理、只校验和必须渲染复核的规则具有明确边界。
  - 正文与表格内容保持不变，平台文件接口保持兼容。
  - 无渲染器时不得把分页、版记偶数页和印章位置报告为已通过。
- 执行计划:
  - 第一批建立标准参数、段落角色识别和页面版式模块，并接入现有确定性格式化器。
  - 后续批次实现附件、落款、版记与合规报告，再对真实样例做结构和渲染复核。
- 阶段验证:
  - 第一批已完成标准常量、段落角色、A4 页面网格和奇偶页动态页码模块，并接入格式化器。
  - 公文格式化、角色、页面、OpenAI-compatible、远程文件和网关聚焦测试 23 项通过。
  - 采购请示原版结构验证通过：正文与表格内容不变，页边距、页脚距离、560 网格及
    奇偶页 `PAGE` 域均已写入；当前仍未进行分页和印章位置的渲染复核。
  - Ruff、Python 编译检查和 `git diff --check` 通过。
  - 第二批已完成附件说明悬挂对齐、正式附件另面、附件标题第三行、落款日期右空四字、
    版记边线与同页属性；已有半角前导空格会折算缩进，原文字符保持不变。
  - 合规报告已区分静态检查与渲染未验证项，平台文件字段保持不变。
  - `公文格式规范.docx` 正文快照和采购请示结构金标准通过；第二批聚焦回归 26 项通过。
  - README、运行调试手册、智能体登记表和架构决策已同步自动格式化、静态校验与渲染
    复核边界；最终聚焦回归 26 项、Ruff、Python 编译和 `git diff --check` 均通过。
- 最后更新: 2026-07-30

### T-048 按公文格式规范修正标题缩进

- 状态: Done
- 目标: 以 `临时文件/公文格式化配置/公文格式规范.docx` 为依据，将正文各结构层级
  的段首统一为空两个中文字符，同时保持主标题和主送机关原有对齐规则。
- 验收标准:
  - 一级至四级标题以及正文、附件说明均写入 `firstLine=640` 和 `firstLineChars=200`。
  - 主标题居中且不缩进，主送机关居左顶格。
  - 采购请示重新生成后文字和表格内容与原版完全一致。
  - 聚焦测试和静态检查通过。
- 验证:
  - 从规范文件确认层级段落使用 `firstLine=640`、`firstLineChars=200`，不是向文字插入空格。
  - 公文格式化、平台文件、远程文件和网关聚焦测试 18 项通过，Ruff 通过。
  - 采购请示六个一级标题均写入双重 2 字符缩进属性，主标题和主送机关保持不缩进，
    正文与表格内容和原版完全一致。
- 最后更新: 2026-07-30

### T-047 公文格式化第一版规则增强

- 状态: Done
- 目标: 按 `临时文件/公文格式化配置/SKILL.md` 完成纯格式化第一版，直接处理 DOCX，
  不引入 LLM，不改写正文和表格内容。
- 验收标准:
  - 显式设置 A4、标准页边距、28 磅固定行距和 640 twips 正文首行缩进。
  - 正确应用主标题、主送机关、一二级标题、正文、附件、落款和日期格式。
  - 表格使用三线表，表头居中，名称/规格列左对齐，序号/数量列居中，金额列右对齐。
  - 删除旧的日期和重复标题清理逻辑，格式化前后正文与表格内容完全一致。
  - 保持现有统一文件接口、OpenAI-compatible 非流式/SSE 和平台文件输出协议。
  - 聚焦测试、样例结构检查和静态检查通过。
- 执行计划:
  - 增强确定性格式化内核并增加内容快照校验。
  - 补充格式角色、A4、表格对齐和内容不变测试。
  - 更新智能体说明和架构决策，运行聚焦回归。
- 验证:
  - 公文格式化、OpenAI-compatible、共享远程文件和网关聚焦测试 18 项通过。
  - Ruff、Python 编译检查和 `git diff --check` 通过。
  - 用户提供的原版 DOCX 结构验证通过：输出为 A4，正文和表格内容完全一致，附件缩进
    640 twips，表格名称/规格左对齐、序号/数量居中、金额右对齐。
- 最后更新: 2026-07-30

### T-046 移除公文格式化服务端字体依赖

- 状态: Done
- 目标: 公文格式化只写入 DOCX 字体名称，删除服务端字体资源、安装、探测和健康告警逻辑。
- 验收标准:
  - 格式化规则中的字体名称保持不变。
  - 智能体源码、返回结果和健康接口不再包含字体探测状态。
  - Docker 镜像不再复制公文字体或执行 `fc-cache`。
  - 字体二进制不再随智能体交付，文档明确字体由用户端提供。
  - 聚焦测试和 Ruff 检查通过。
- 验证:
  - 公文格式化、OpenAI-compatible 和网关聚焦测试共 20 项通过。
  - Ruff 与 `git diff --check` 通过；残留引用检查确认运行时代码和镜像均无字体探测或安装逻辑。
  - 格式规则测试继续验证 DOCX 内写入方正小标宋、黑体、楷体和仿宋字体名称。
- 最后更新: 2026-07-30

### T-049 增强部门知识库长任务进度与原子索引发布

- 状态: Done
- 目标: 让多文档和扫描件保存持续返回可见进度，并通过 staging 构建和原子发布
  避免失败请求破坏当前可检索快照。
- 验收标准:
  - SSE 立即返回空间和意图阶段，保存期间逐文档报告下载、归档、解析/OCR、向量与提交状态，
    并在长步骤中定期发送心跳。
  - 只有新文档快照、Chroma 和 manifest 全部构建并验证成功后才切换为当前版本；
    任一阶段失败均保留旧文档和旧索引。
  - MinIO 原件继续按 SHA-256 幂等归档；失败时明确区分“原件已归档”和“索引未提交”。
  - 服务端记录带请求 ID 和阶段的真实异常，用户响应保持脱敏。
  - 覆盖多文档成功、OCR进度、构建失败回滚、旧索引保持、SSE心跳和兼容调用回归。
- 执行计划:
  - 为知识库核心增加 staging 构建、验证、原子目录切换和失败清理。
  - 为部门保存链路增加结构化进度回调和可恢复阶段语义。
  - 将 SSE 改为后台执行加事件队列，空闲期间发送心跳并记录异常。
  - 更新运行说明、设计决策和问题日志，完成聚焦及必要全量验证。
- 验证:
  - 多文档成功、失败保留旧快照、版本化发布、OCR进度、SSE心跳、失败脱敏和旧协议
    聚焦测试 28 项通过。
  - 部门知识库、共享知识库、网关、附件和 OCR 扩大回归 45 项通过。
  - 全仓 181 项测试通过；全仓 Ruff 和 `git diff --check` 通过。
- 最后更新: 2026-07-30（完成）

### T-048 将最新 Git 更新部署到机器人管理平台服务器

- 状态: Done
- 目标: 参照 `local-deployment` 已验证的 Git bundle 和服务器增量构建流程，
  将 `main` 提交 `6124ed133f39` 部署到 `robotpl-hr-deploy`，保留生产密钥与
  两个知识库卷。
- 验收标准:
  - 服务器精确检出目标提交并构建对应 `linux/amd64` 镜像。
  - Compose 生产服务全部运行，所有网关模型健康，只有 gateway 发布 `10085:8008`。
  - GPU Stack、部门 MinIO、平台 backend 到网关及 gateway dry-run 验证通过。
  - `agent-workspace_knowledge_base_data` 和
    `agent-workspace_department_kb_minio_data` 均保留，不执行 `down -v`。
- 验证:
  - Release `git-6124ed133f39`，镜像
    `agent-workspace:git-6124ed133f39`，镜像 ID
    `sha256:81af3098f9f0fe4a6398939af63e505f21a0b57bae926f4ccdf655c61b90148e`。
  - 12 个 Compose 服务运行，10 个 worker 均 healthy；鉴权模型发现返回 10 个模型。
  - GPU Stack、部门 MinIO、平台 backend 到网关均返回 200，gateway dry-run 成功。
  - 只有 gateway 发布 `10085:8008`，两个知识库命名卷均存在。
- 最后更新: 2026-07-30（完成）

### T-047 修复部门知识库附件原始文件名传递

- 状态: Done
- 目标: 让部门知识库兼容平台结构化 `file_url` 附件并使用 PG 中的可信原始文件名，
  同时保留旧 URL、`附件：` 文本和顶层 `files` 调用。
- 验收标准:
  - 共享附件解析能保留 URL、原始文件名和来源方式，并优先采用带原名的重复引用。
  - 部门知识库下载临时 URL 时使用可信原名保存快照和归档对象，不保存签名 URL。
  - 原有字符串 `files`、正文 URL、旧 content parts 和 dry-run 行为不回归。
  - 本地 AI 应用平台的“项目交付部知识库”切换到结构化附件模式。
  - 通过本地平台真实上传并保存一个非 UUID 原名文件，最终知识库显示正确原名。
- 执行计划:
  - 扩展共享附件解析并在部门知识库内部统一为附件引用对象。
  - 补充协议、存储和兼容测试，运行定向回归。
  - 重建本地 Compose，切换平台模型配置并执行 10081 端到端验证。
- 验证:
  - 文件型智能体共享附件回归 61项通过，聚焦 Ruff通过，`git diff --check`通过。
  - 本地部门 worker和 gateway使用新镜像重建，部门 worker保持 healthy。
  - 平台模型配置7“项目交付部知识库”已使用
    `attachment.mode=file_url_content_part`，并固定
    `knowledge_id=project-delivery`。
  - 通过 10081以机器人账号真实上传 `原始文件名验证_20260730.txt`，平台返回可信
    原名和 `file_id`；保存请求识别为 `save`并写入1个分块。
  - 本地快照、manifest及 `department-kb-project-delivery` bucket均包含正确中文
    原名；MinIO对象键不含预签名查询参数。
- 最后更新: 2026-07-30（完成）

### T-046 将 Git 更新部署到机器人管理平台服务器

- 状态: Done
- 目标: 参照 `local-deployment` 已验证流程，把 `main` 提交 `804858173ca9`
  以 Git bundle 和服务器构建方式部署到 `robotpl-hr-deploy`，新增公文格式化
  Agent，同时保留生产密钥和知识库卷。
- 验收标准:
  - 服务器精确检出目标提交，构建 `linux/amd64` 镜像且系统字体可被 Fontconfig 识别。
  - Compose 生产服务全部运行，10 个模型健康，只有 gateway 发布 `10085:8008`。
  - GPU Stack、部门 MinIO、平台 backend 到网关及 gateway dry-run 验证通过。
  - `agent-workspace_knowledge_base_data` 和
    `agent-workspace_department_kb_minio_data` 均保留，不执行 `down -v`。
- 验证:
  - Release `git-804858173ca9`，镜像
    `agent-workspace:git-804858173ca9`，镜像 ID
    `sha256:2851099367a0e241a3a3ce7938d852cc38503f4b831c5779ef37b02d522490e6`。
  - 12 个 Compose 服务运行，10 个 worker 均 healthy；鉴权模型发现返回 10 个模型。
  - `fc-cache` 和公文字体匹配通过；GPU Stack、部门 MinIO、平台到网关均返回 200。
  - 仅 gateway 发布 `10085`，两个知识库命名卷均存在。
- 最后更新: 2026-07-30

### T-045 创建确定性公文格式化智能体

- 状态: Done
- 目标: 将已经过公司验证的 `format_docx` 脚本封装为 Linux 可部署的 LangGraph 智能体，只做 DOCX 格式化，不进行内容润色，并通过统一网关返回可由 AI 平台持久化的 `delta.file`。
- 验收标准:
  - 源码位于 `src/agents/official_document_formatting/`，格式化核心保持现有字体、字号、边距、行距、缩进、标题识别、表格和去重规则。
  - 支持本地路径、HTTP(S) DOCX、平台 `附件：` 和 `file_url.url`，一次只处理一份 DOCX。
  - 支持 dry-run、CLI、OpenAI-compatible 非流式和 SSE；正式结果在 `message.file` / `delta.file` 中返回 DOCX Base64、文件名、MIME 和 SHA-256。
  - 模型 ID `official-document-formatting-agent` 注册到统一网关，Compose worker 只监听内部 `8080`，生产仍只发布网关端口。
  - 服务端不依赖公文字体即可完成 DOCX 格式化，字体名称规则保持不变。
  - 定向测试、网关测试、Ruff、配置检查和必要全量回归通过。
- 执行计划:
  - 冻结格式化内核，先补确定性格式测试。
  - 实现 LangGraph、服务层和 CLI。
  - 实现 OpenAI-compatible 文件协议、网关和 Compose 注册。
  - 更新文档并执行聚焦与全量验证。
- 验证:
  - 公文格式化智能体、OpenAI-compatible 文件协议和网关聚焦测试共 20 项通过。
  - 新增 Python 代码 Ruff 检查通过，`git diff --check` 通过，JSON/YAML 可解析。
  - 全量回归完成 153 项通过；其余 18 项受当前基础环境缺少 `pytest-asyncio`、`minio`、历史测试样例和 Chroma SQLite 运行条件影响，均不涉及本次新增智能体。
  - 当前机器未安装 Docker CLI，未执行本地 Compose 启动验证；Compose 服务和依赖配置已完成静态检查。
- 最后更新: 2026-07-29

### T-044 将生成视频持久化到 AI 平台对象存储

- 状态: Done
- 目标: 视频 Agent 只返回结构化的 ComfyUI 内部产物地址，由 AI 平台后端完成受控下载、格式校验、MinIO 持久化和用户文件映射，浏览器不再依赖访问 ComfyUI 内网地址。
- 验收标准:
  - Agent 用户正文不包含 `COMFYUI_VIDEO_PUBLIC_BASE_URL`，最终响应保留兼容字段并新增 `video.source_url`。
  - AI 平台后端仅从显式白名单来源下载 MP4，限制大小、超时和重定向，写入现有 MinIO 与 `file_mapping`。
  - 流式接口返回平台资产 `video_delta`，前端使用平台 URL 播放或下载。
  - Agent 与 AI 平台聚焦测试通过。
- 验证:
  - Agent 协议修改及聚焦测试9项通过；正文不再含 ComfyUI地址，非流式和SSE均返回 `source_url`。
  - AI平台新增 MP4真实格式、大小、超时、重定向及来源白名单校验，持久化到现有 MinIO和 `file_mapping`，并在失败时回滚清理对象。
  - AI平台后端视频服务与流式回归25项通过，Ruff通过；前端 `video_delta` 测试4项通过，Vue TypeScript检查通过。
- 最后更新: 2026-07-29

### T-043a 创建部门隔离知识库智能体群

- 状态: Done
- 目标: 复用工作区知识库核心，新建一个通过 `knowledge_id` 切换八个部门知识库空间的
  OpenAI-compatible 智能体；使用 GPU Stack Qwen3.5 识别保存、问答等意图，并以可复用
  PaddleOCR-VL-1.6 组件处理扫描文档。
- 验收标准:
  - 八个部门使用固定白名单映射和独立知识库目录，用户文本不能覆盖或推导
    `knowledge_id`，未知值直接拒绝。
  - 同一 `POST /v1/chat/completions` 支持 `knowledge_id`、附件 URL/content parts、
    非流式和 SSE；识别到保存意图且存在附件时才持久化并入库。
  - 文本型 PDF、DOCX、Markdown、TXT 优先本地解析；扫描 PDF和图片通过可扩展 OCR
    provider 调用 GPU Stack `paddleocr-vl-1.6`。
  - 新 worker 注册到统一网关并加入根 Compose，只使用内部 `8080`，生产仍只发布网关端口。
  - 补充定向测试、环境变量模板、登记表、运行手册、网关说明、设计决策和对象存储建议。
- 执行计划:
  - 复用 `KnowledgeBaseManager` 和共享附件传输，补足受控文件保存与 OCR loader 扩展点。
  - 实现部门目录、Qwen3.5 意图分类、LangGraph 工作流和 OpenAI-compatible worker。
  - 注册网关/Compose，补齐配置、文档和测试。
  - 运行定向测试、Ruff、Compose 配置及必要回归。
- 验证:
  - 部门知识库、共享 OCR、知识库核心和网关定向测试 32项通过；全仓测试 148项通过，
    Ruff全仓和 `git diff --check` 通过。
  - GPU Stack真实模型发现确认 `qwen3.5-122b-a10b` 与 `paddleocr-vl-1.6`；实际意图
    请求返回 `save`，实际文字页 OCR返回非空结果。
  - 项目专属 MinIO以固定镜像启动并健康，真实对象归档/校验/清理通过；完整临时链路
    完成原件归档、本地快照、GPU嵌入、Chroma manifest并清理测试数据。
  - 本机 Compose共 11个运行服务（含本机代理 sidecar、八个 worker、gateway和专属
    MinIO），全部健康或正常运行；只有 gateway发布宿主机 `8008`。
  - 鉴权网关 `/v1/models` 返回八个模型；新模型 dry-run保存路由、真实 Qwen查询路由、
    `knowledge_id`作用域和对象存储配置均验证通过。
- 最后更新: 2026-07-28（完成）

### T-043 创建直连 ComfyUI 的视频生成智能体

- 状态: Done
- 目标: 在工作区内新增符合统一网关规范的 LangGraph 文生视频智能体，由 worker 直接调用 ComfyUI，不再依赖单独部署的 Videos API。
- 验收标准:
  - 源码位于 `src/agents/comfyui_video_generation/`，安全渲染内置 LTX 2.3 API 工作流。
  - 支持 OpenAI-compatible 非流式与 SSE Chat Completions，进度使用 `reasoning_content`。
  - `dry_run=true` 不调用 ComfyUI；正式请求直接访问 `COMFYUI_VIDEO_BASE_URL`。
  - 模型 ID `comfyui-video-generation-agent` 注册到统一网关，Compose worker 不发布额外宿主机端口。
  - 配置、Agent 登记、运行手册、架构决策和自动化测试同步完成。
- 执行计划:
  - 实现输入解析、受限参数模型、内置工作流渲染和直连 ComfyUI 客户端。
  - 实现 LangGraph、服务层与 OpenAI-compatible worker。
  - 注册网关与 Compose，更新环境和运维文档。
  - 运行定向、全量、静态与配置验证。
- 验证:
  - 新 Agent 与网关定向测试 20 项通过；覆盖解析、工作流白名单、ComfyUI提交/历史输出、节点错误、普通响应、SSE、dry-run、健康状态和未知模型。
  - 全仓测试 136 项通过；8 项既有测试因缺少 `临时文件/仅包含一行文字的文件.docx` 和当前替代环境 Chroma SQLite 无法创建而失败，与本任务无关。
  - 新 Agent 的 `compileall`、网关 JSON解析、Compose YAML结构和 `git diff --check` 通过；静态检查确认只有 gateway 发布端口，视频 worker 仅 expose内部8080。
  - ComfyUI目标地址已按实际环境调整为 `http://10.180.26.16:8188`；保留环境变量覆盖能力，未为验收额外提交GPU任务。
  - 新增 `scripts/test_ai_app_video_agent.py`，按 `ai-app-platform` 后端上游模型协议测试OpenAI-compatible SSE链路，并可下载最终视频。
  - 测试脚本无需应用ID或登录凭证；请求体、SSE解析、可选网关鉴权和正文错误识别测试通过。
  - 通过代理读取目标 ComfyUI 0.28.0 节点选项，并同步内置工作流的实际 LoRA 与文本编码器文件名。
  - 使用 `comfyui` Conda环境和 `127.0.0.1:7897` 代理完成真实生成；任务 `video_a5c6b2c729b649a8842c2521efb87bff` 成功，成品下载为工作区 `cat.mp4`。
  - 在同一 `comfyui` 环境安装最小测试依赖后，视频脚本、视频 Agent与网关聚焦回归共25项通过。
  - 当前机器没有 Ruff，PowerShell与WSL均无 Docker CLI；未执行 Ruff和原生 `docker compose config`，已记录到问题日志。
- 最后更新: 2026-07-28

### T-042 将统一智能体网关部署到机器人管理平台服务器

- 状态: Done
- 目标: 复用已验证的离线镜像发布经验，把当前 `agent-workspace` Compose 部署到机器人管理平台服务器，并保留可校验、可回滚、可复现的发布记录。
- 验收标准:
  - 发布镜像为目标服务器兼容的 `linux/amd64`，发布包包含 SHA-256 校验且不包含真实密钥。
  - 通过 `robotpl` 将发布包传到 `/opt/agent-workspace/releases/<release-id>/`，远端校验后导入镜像。
  - 生产环境不启用本机 `local-proxy` profile，容器可直接访问 GPU Stack。
  - 不迁移本机知识库命名卷；远端首次启动创建空的 `knowledge_base_data` 卷。
  - 远端仅发布宿主机端口 `10085` 到网关容器 `8008`，七个 worker 健康，`/health` 与 `/v1/models` 验证通过。
  - 形成服务器部署、升级和回滚说明，且不执行 `docker compose down -v`。
- 执行计划:
  - 核对本机 WSL/Docker、目标服务器架构、端口、磁盘和 GPU Stack 网络。
  - 生成不含卷和密钥的发布包，导出镜像并生成 SHA-256。
  - 使用 rsync 断点续传，远端校验、导入并以生产配置启动。
  - 从远端宿主机和容器内验证网关、worker、模型连通性及公开端口。
- 验证:
  - 发布版本为 `20260727-1243-fcbbba248cd8`，镜像
    `sha256:fcbbba248cd81123807fb17e409154175392ee6a365ba391a93d96ad53df1e05`，
    `linux/amd64`；383 MiB 压缩发布包在服务器通过 SHA-256 校验。
  - 发布包已上传到
    `/opt/agent-workspace/releases/20260727-1243-fcbbba248cd8/`，服务器使用
    `--no-build --pull never` 启动，不含本机知识库卷。
  - 远端创建空卷 `agent-workspace_knowledge_base_data`，8 个生产服务运行，七个
    worker 均为 healthy；只有 gateway 发布 `10085:8008`。
  - `/health` 返回 200 并报告七个模型健康；未授权 `/v1/models` 返回 401，带生产
    密钥返回七个模型。
  - `contract-review-agent` 非流式 Chat Completions 冒烟请求成功；从
    `image-generation` 容器访问 GPU Stack `/v1/models` 返回 200 和五个预期模型。
  - 现有 `ai-app-platform-backend-1` 容器访问
    `http://10.100.5.23:10085/health` 返回 200，平台容器到新网关路径可达。
- 最后更新: 2026-07-27（完成）

### T-041 增强图片智能体流式生成进度

- 状态: Done
- 目标: 让 `image-generation-agent` 在耗时的提示词改写和图片生成期间持续返回可见进度，降低平台等待感。
- 验收标准:
  - 流式请求立即返回角色和解析状态。
  - `thinking=true` 时，模式选择、提示词改写结果、开始生成和等待心跳进入 `delta.reasoning_content`。
  - 不输出模型隐藏思维链；最终图片仍只通过一次 `delta.content` 多模态数组返回。
  - 非流式接口、错误脱敏和现有图片生成/编辑行为不回归。
- 执行计划:
  - 从 LangGraph节点更新产生结构化进度事件。
  - 接入 OpenAI-compatible SSE并补协议测试。
  - 更新运行说明并运行定向与全量回归。
- 验证:
  - 图片智能体定向测试14项通过；完整测试137项通过，Ruff和 `git diff --check` 通过。
  - 真实 Compose网关流式文生图验证首个 delta约0.016秒返回。
  - 实际事件顺序包含解析输入、模式选择、最终改写提示词、开始生成、5秒心跳和结果整理；最终 content类型仍为 `text`、`image_url`。
  - 验证脚本只输出文字进度与 content类型，不输出图片 Base64。
- 最后更新: 2026-07-27（完成）

### T-040 创建 GPU Stack 对话式图片生成智能体

- 状态: Done
- 目标: 新建 `image-generation-agent`，使用 Qwen3.5 视觉改写提示词，并按是否存在底图路由到 `qwen-image` 或 `qwen-image-edit`；同时迁移工作区 DeepSeek 与知识库嵌入默认配置到 GPU Stack。
- 验收标准:
  - 智能体支持 HTTP(S) 图片、Base64 data URL、原始 Base64及自动沿用最近生成图。
  - OpenAI-compatible 非流式和 SSE均能返回文本与 `image_url` 多模态 content parts。
  - 统一网关注册新模型且生产环境仍只公开 `8008`。
  - 知识库问答使用 `deepseek-v4-flash`，嵌入使用 `qwen3-vl-embedding-8b`，旧向量不会与新向量混用。
  - 形成可直接交给 AI 应用平台 Agent 的图片输出 handoff。
- 执行计划:
  - 迁移共享 GPU Stack配置与知识库默认模型。
  - 实现图片输入、安全规范化、LangGraph工作流和 GPU Stack客户端。
  - 增加 OpenAI-compatible worker、网关/Compose注册、测试和文档。
  - 运行本地、WSL Docker及真实 GPU Stack契约验证。
- 验证:
  - 图片智能体与共享配置定向测试16项通过；移除已失效的旧批量简历测试后，全仓回归136项通过，Ruff全仓通过。
  - GPU Stack真实契约验证通过：五个模型 ID精确匹配；`qwen3-vl-embedding-8b` 返回 4096维向量；Qwen3.5文本/视觉改写、`qwen-image` 文生图和 `qwen-image-edit` 连续编辑均成功。
  - 真实两轮网关响应均为 `text + image_url` 多模态数组，图片使用 data URL；验证过程未输出 Key或 Base64。
  - 本机 Compose profile含 9个服务（含本机代理 sidecar），使用 `.env.example` 模拟服务器时含 8个服务且不含 sidecar；两种 `docker compose config --quiet` 均通过。
  - 网关 `/v1/models` 返回七个健康智能体模型且仅发布 `8008`；知识库卷盘点为0个文件，无旧向量需要备份或重建。
  - AI应用平台图片输出与持久化改造已形成 `docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`。
- 最后更新: 2026-07-24（完成）

### T-039 将统一网关公共端口迁移至 8008

- 状态: Done
- 目标: 将统一 OpenAI-compatible 网关的代码默认值、Compose 发布、平台地址、运行手册和技能统一由 `8004` 迁移为 `8008`。
- 验收标准:
  - 网关开发/服务默认端口和 Compose 唯一公开端口均为 `8008`。
  - 平台 backend 容器可以通过 `172.27.0.1:8008/v1` 获取模型列表。
  - 当前运行文档、智能体 README、登记表、skills 和环境账本不再把 `8004` 作为当前统一入口。
- 验证:
  - `tests/agent_gateway` 10 项通过，`ruff check src/agent_gateway scripts/verify_agent_gateway_isolation.py` 通过。
  - `docker compose config --quiet` 通过；已重建 gateway，宿主机发布 `8008:8008`，网关返回 6 个模型。
  - `ai-app-platform-backend-1` 容器已通过 `http://172.27.0.1:8008/v1/models` 返回 6 个模型。
  - 故障隔离脚本在 `8008` 验证通过：停止 worker 后模型数为 5、其他 worker 可调用、恢复后重新为 6。
  - 旧网关端口 `8004` 的精确残留扫描为空，`git diff --check` 和相关 Ruff 通过。
- 最后更新: 2026-07-14（完成）
- 最后更新: 2026-07-14

### T-038 同步全部智能体 README 的统一入口说明

- 状态: Done
- 目标: 让每个智能体 README 准确说明当前统一网关、模型 ID、独立调试入口、容器网络边界和知识库/兼容包例外。
- 验收标准:
  - 全部现存智能体目录 README 说明生产平台入口是否为当前统一网关端口，不再把旧独立 OpenAI 端口写成推荐配置。
  - 未注册到网关的智能体明确说明现状和端口冲突。
  - 共享附件、鉴权和容器内 `127.0.0.1` 的关键约束在文件型平台智能体 README 可见。
  - 文档链接指向统一网关运行手册，且残留扫描通过。
- 验证:
  - 已更新 `batch_resume_review_llm`、`tender_format_review`、`smart_resume_screening`、`contract_review`、`official_document_review`、`langchain_knowledge_base` 和 `resume_review` 的 README。
  - 残留扫描确认根智能体 README 不再把 8006–8014 作为生产 Base URL；唯一保留的 `8006` Base URL 位于脱离工作区的独立发行模板，已明确其不适用于工作区生产部署。
  - `git diff --check` 通过。
- 最后更新: 2026-07-14（完成）

### T-037 更新统一网关与智能体创建 skills

- 状态: Done
- 目标: 将 T-036 的统一 OpenAI-compatible 网关、容器网络、共享附件和可复用知识库经验沉淀到现有 skills。
- 验收标准:
  - `openai-compatible-llm-wrapper` 覆盖 gateway 注册、健康/错误语义、共享附件、安全配置、Compose 与平台网络验证。
  - `langchain-agent-builder` 覆盖新智能体加入统一网关、知识库 namespace 和验证流程。
  - 两个 skill 的 `SKILL.md` 与 `agents/openai.yaml` 同步并通过 skill 校验。
- 执行计划:
  - 根据已验证的 Compose 和容器调用路径重写两个 skill 的部署与接入章节。
  - 更新 UI 默认提示词，运行 skill 基础校验，并记录验证结果。
- 验证:
  - `quick_validate.py .codex\skills\openai-compatible-llm-wrapper` 输出 `Skill is valid!`。
  - `quick_validate.py .codex\skills\langchain-agent-builder` 输出 `Skill is valid!`。
  - 两个 `agents/openai.yaml` 已同步统一网关导向的默认提示词。
- 最后更新: 2026-07-14（完成）

### T-036 建立多智能体 OpenAI-compatible 统一网关

- 状态: Done
- 目标: 以统一公共端口为唯一对外入口，按 OpenAI 请求中的模型名路由到隔离部署的智能体，并重做可复用、按命名空间隔离的知识库能力。
- 验收标准:
  - `GET /v1/models` 仅列出健康模型，`POST /v1/chat/completions` 支持非流式和 SSE 透传。
  - 生产 Compose 只发布网关公共端口，各 worker 使用内部 `8080`，单个 worker 停止不影响网关和其他模型。
  - 本机开发可通过一个命令启动、监管和重启所选 worker，无需手工维护端口。
  - `batch_resume_review_llm` 成为批量简历唯一业务实现，旧包名与对应过时测试已移除。
  - 知识库移除 primary/secondary 和独立项目残留，按 agent namespace 与 knowledge-base name 隔离数据。
  - 现有 OpenAI-compatible 回归、新网关、知识库、附件安全和 Compose 配置验证通过。
- 执行计划:
  - 实现声明式模型注册、健康状态、鉴权和流式反向代理。
  - 实现跨平台开发监管器和 Linux Docker Compose 部署。
  - 收敛共享 OpenAI/附件能力与批量简历重复实现。
  - 破坏性重做知识库核心、适配器和测试。
  - 更新登记表、运行手册、平台接入、依赖、决策和环境账本。
- 验证:
  - 网关、监管器、新知识库、共享附件及六个包装器定向测试共 96 项通过。
  - 正式 `tests/` 全量 146 项通过，包含网关、知识库、附件、六个包装器、参考数据和 canonical 独立打包。
  - Linux 镜像构建成功，`docker compose config --quiet` 成功，宿主机只发布 `8004`，六个 worker 健康。
  - 故障隔离脚本验证停止 `contract-review` 后模型列表从 6 降为 5、其他模型可用，恢复后重新为 6。
  - `ruff check .` 全量通过；最终 Compose 状态显示六个 worker 全部 healthy，`/v1/models` 返回六个模型。
- 最后更新: 2026-07-14（完成）

### T-035 将知识库智能体纳入工作区统一 Git 追踪

- 状态: Done
- 目标: 为整体多智能体工作区创建 GitHub 仓库做好准备，使 `langchain_knowledge_base` 与其他智能体由同一个根 Git 仓库追踪。
- 验收标准:
  - 已移除 `src/agents/langchain_knowledge_base/.git` 嵌套仓库元数据，知识库源代码可由根仓库识别和提交。
  - 本地密钥、Chroma 数据和测试/静态检查缓存仍被忽略，不会进入提交。
  - README、运行手册、智能体登记表、密钥说明和决策记录不再将知识库描述为独立 Git 子项目。
  - 知识库 API、测试、eval 和 Docker Compose 命令均从工作区根目录执行。
- 验证: 根目录 `git status --short` 显示 `src/agents/langchain_knowledge_base/` 为普通待追踪目录；`git -C src/agents/langchain_knowledge_base rev-parse --show-toplevel` 指向工作区根目录；根目录启动使用 `uvicorn kb_api.main:app --app-dir src/agents/langchain_knowledge_base`。
- 最后更新: 2026-07-13

### T-034 放宽简历类 OpenAI-compatible JD 解析

- 状态: Done
- 目标: 按 handoff 先修 `batch-resume-review-llm`，再检查其它类似简历类 OpenAI-compatible 入口，避免“Markdown 岗位要求正文 + 附件 URL”因缺少显式 `岗位要求：` 标签而返回 readiness。
- 验收标准:
  - `batch_resume_review_llm` 在已识别简历文件但未识别显式 `岗位要求` / `JD` 区块时，把 `附件`、`简历文件` 或 `输出要求` 之前的正文作为岗位要求。
  - `smart-resume-screening` 同步支持该 fallback，不丢失附件前岗位要求正文。
  - 原显式 `岗位要求：` 协议、附件 URL、content parts 文件 URL 和缺少必要输入时 readiness 行为不回归。
- 执行计划:
  - 在共享 OpenAI-compatible 输入解析工具中增加“首个文件区块前正文”提取函数。
  - 先接入 `batch_resume_review_llm` 并补平台真实形态测试。
  - 将同类逻辑接入 `smart_resume_screening` 并补测试。
  - 更新 README、运行手册、技能说明和决策记录。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_batch_resume_review_llm.py tests\agents\test_smart_resume_screening_llm.py -q` 通过，22 个测试通过。
  - `conda run -n langchain python -m pytest tests\agents\test_batch_resume_review_llm.py tests\agents\test_smart_resume_screening_llm.py tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py tests\agents\test_tender_format_review_llm.py -q` 通过，46 个测试通过。
  - `conda run -n langchain ruff check src\agents\openai_compatible_inputs.py src\agents\batch_resume_review_llm\openai_compatible_api.py src\agents\smart_resume_screening\openai_compatible_api.py src\agents\contract_review\openai_compatible_api.py src\agents\official_document_review\openai_compatible_api.py src\agents\tender_format_review\openai_compatible_api.py tests\agents\test_batch_resume_review_llm.py tests\agents\test_smart_resume_screening_llm.py tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py tests\agents\test_tender_format_review_llm.py` 通过。
- 最后更新: 2026-07-07

### T-033 增强 OpenAI-compatible 文件输入兼容性

- 状态: Done
- 目标: 按 handoff 先增强 `batch-resume-review-llm`，再让其它需上传文件的 OpenAI-compatible 智能体兼容平台 `附件：` 列表和 OpenAI content parts 文件 URL。
- 验收标准:
  - `batch_resume_review_llm` 保留原 `岗位要求`、`简历文件`、JSON 数组和多行 URL 解析，并新增 `附件：` 区块、`file_url.url`、`image_url.url` 支持。
  - `smart-resume-screening`、`contract-review`、`official-document-review`、`tender-format-review` 的 OpenAI-compatible 入口也能解析 `附件：` 区块和 content parts 文件 URL。
  - 缺少必要业务输入时仍返回 readiness，不误触发审查。
  - 增加定向测试并同步 README、运行手册和智能体登记表。
- 执行计划:
  - 新增共享 OpenAI-compatible 文件输入解析工具。
  - 先改 `batch_resume_review_llm` 并补 handoff 指定测试。
  - 推广到其它文件上传型 LLM 入口并补解析测试。
  - 运行定向 pytest 与 Ruff。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_batch_resume_review_llm.py tests\agents\test_smart_resume_screening_llm.py tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py tests\agents\test_tender_format_review_llm.py -q` 通过，43 个测试通过。
  - `conda run -n langchain ruff check src\agents\openai_compatible_inputs.py src\agents\batch_resume_review_llm\openai_compatible_api.py src\agents\smart_resume_screening\openai_compatible_api.py src\agents\contract_review\openai_compatible_api.py src\agents\official_document_review\openai_compatible_api.py src\agents\tender_format_review\openai_compatible_api.py tests\agents\test_batch_resume_review_llm.py tests\agents\test_smart_resume_screening_llm.py tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py tests\agents\test_tender_format_review_llm.py` 通过。
- 最后更新: 2026-07-07

### T-032 将合同审查与公文格式检查智能体封装为 OpenAI-compatible LLM

- 状态: Done
- 目标: 确认近期新增智能体中尚未 OpenAI-compatible 包装的对象，并为 `contract-review`、`official-document-review` 增加 FastGPT/Dify 可用的 LLM 入口。
- 验收标准:
  - `contract-review` 新增 `openai_compatible_api.py`，模型 ID 为 `contract-review-agent`。
  - `official-document-review` 新增 `openai_compatible_api.py`，模型 ID 为 `official-document-review-agent`。
  - 两个入口均提供 `GET /v1/models` 和 `POST /v1/chat/completions`。
  - 支持非流式和流式 SSE，普通模型探测提示返回 readiness。
  - 增加定向测试并同步登记表、运行手册。
- 执行计划:
  - 盘点 `contract-review`、`official-document-review`、`smart-resume-screening` 的包装状态。
  - 为未包装的两个智能体新增薄包装 FastAPI app。
  - 补充模型列表、非流式 dry-run、流式 dry-run、thinking=false 和模型探测测试。
  - 运行定向 pytest 和 Ruff。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py -q` 通过，10 个测试通过。
  - `conda run -n langchain ruff check src\agents\contract_review\openai_compatible_api.py src\agents\official_document_review\openai_compatible_api.py tests\agents\test_contract_review_llm.py tests\agents\test_official_document_review_llm.py` 通过。
- 最后更新: 2026-07-07

### T-031 将智能简历结构化初筛智能体封装为 OpenAI-compatible LLM

- 状态: Done
- 目标: 为 `smart-resume-screening` 增加面向 FastGPT/Dify 自定义 LLM 节点的 OpenAI-compatible 入口。
- 验收标准:
  - 保留原 CLI/API/MCP 入口不变，新增 `openai_compatible_api.py`。
  - 提供 `GET /v1/models` 和 `POST /v1/chat/completions`，模型 ID 为 `smart-resume-screening-agent`。
  - 支持 `stream=false` 和 `stream=true`，流式输出 SSE chunk 并以 `[DONE]` 结束。
  - 普通模型探测提示返回 200 readiness 文本，不因缺少业务输入返回 400。
  - 可从 prompt 的“岗位要求”和“简历文件”区块解析本地路径、多行链接或 FastGPT JSON 数组。
  - 增加定向测试，并同步登记表和运行手册。
- 执行计划:
  - 参考 `openai-compatible-llm-wrapper` skill 和现有批量简历 LLM 适配器。
  - 新增薄包装 FastAPI app，复用 `screen_resumes` 服务层。
  - 补充非流式、流式、模型探测、thinking=false 和 JSON 数组解析测试。
  - 更新相关文档和任务状态。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_smart_resume_screening_llm.py -q` 通过，6 个测试通过。
  - `conda run -n langchain ruff check src\agents\smart_resume_screening\openai_compatible_api.py tests\agents\test_smart_resume_screening_llm.py` 通过。
- 最后更新: 2026-07-07

### T-030 基于 FastGPT 智能简历筛选工作流创建结构化初筛智能体

- 状态: Done
- 目标: 将 `智能简历筛选(1).json` 中岗位基本信息、硬性条件、加分项、淘汰项、量化评分和排行榜输出的经验转化为本工作区轻量智能体。
- 验收标准:
  - 新增 `smart-resume-screening` 智能体，源码位于 `src/agents/smart_resume_screening/`。
  - 智能体保留 FastGPT 工作流中结构化招聘条件与评分排行的经验，但不复制单一长提示词。
  - 支持多份 DOCX、文本型 PDF、TXT、MD 简历解析与 dry-run。
  - 支持 CLI、REST API 和 MCP。
  - 补充最小测试、样例、README、工作区登记表、运行手册和环境变量模板。
- 执行计划:
  - 解析 `智能简历筛选(1).json` 的系统提示词和输入/输出规格。
  - 创建岗位条件解析、候选人加载、确定性初筛评分和报告整理工作流。
  - 增加 CLI/API/MCP 入口和 dry-run 测试。
  - 同步任务板、登记表、运行手册和设计决策。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_smart_resume_screening.py -q` 通过，7 个测试通过。
  - `conda run -n langchain ruff check src\agents\smart_resume_screening tests\agents\test_smart_resume_screening.py` 通过。
  - 内置样例 CLI dry-run 成功，生成 `临时文件\智能简历筛选_dry_run.md`。
- 最后更新: 2026-07-07

### T-029 基于 FastGPT 公文优化工作流创建公文格式检查智能体

- 状态: Done
- 目标: 将 `公文优化.json` 中“上传单份文件、调用格式检测、整理检测结果”的经验转化为本工作区的 LangChain / LangGraph 智能体。
- 验收标准:
  - 新增 `official-document-review` 智能体，源码位于 `src/agents/official_document_review/`。
  - 智能体保留 FastGPT 工作流中文件检测与报告美化的分层经验，但不依赖原内网 HTTP 检测地址。
  - 支持 DOCX、文本型 PDF、TXT、MD 的解析与 dry-run。
  - 支持 CLI、REST API 和 MCP。
  - 补充最小测试、样例、README、工作区登记表、运行手册和环境变量模板。
- 执行计划:
  - 解析 `公文优化.json` 的节点、输入、HTTP 检测和输出提示词。
  - 创建本地公文解析、确定性格式检查、报告整理 LangGraph 工作流。
  - 增加 CLI/API/MCP 入口和 dry-run 测试。
  - 同步任务板、登记表、运行手册和设计决策。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_official_document_review.py -q` 通过，7 个测试通过。
  - `conda run -n langchain ruff check src\agents\official_document_review tests\agents\test_official_document_review.py` 通过。
  - 内置样例 CLI dry-run 成功，生成 `临时文件\公文格式检查_dry_run.md`。
- 最后更新: 2026-07-07

### T-028 基于 FastGPT 合同审查工作流创建合同审查智能体

- 状态: Done
- 目标: 阅读用户提供的 FastGPT 导出 JSON，选择适合转化的工作流，吸收其中有效经验并在本工作区创建一个对应的 LangChain / LangGraph 智能体。
- 验收标准:
  - 已盘点 `C:\Users\Lenovo\Desktop\智能配置文件体\` 下 FastGPT 导出工作流，并说明首选转化对象。
  - 新增 `contract-review` 智能体，源码位于 `src/agents/contract_review/`。
  - 智能体保留合同审查大师中较好的表单上下文、六维审查、评分评级和整改建议经验，但不照抄 FastGPT 节点流程。
  - 支持 CLI、REST API、MCP 和 dry-run 验证。
  - 补充最小测试、样例、README、工作区登记表、运行手册、环境变量模板和设计决策。
- 执行计划:
  - 阅读工作区文档、任务台账和 `langchain-agent-builder` skill。
  - 解析 FastGPT JSON 的节点、输入、边和提示词轮廓，选择首个转化对象。
  - 创建合同解析、分块、六维审查、评分汇总、CLI/API/MCP 入口。
  - 增加 dry-run 测试并同步文档。
- 验证:
  - `conda run -n langchain python -m pytest tests\agents\test_contract_review.py -q` 通过，8 个测试通过。
  - `conda run -n langchain ruff check src\agents\contract_review tests\agents\test_contract_review.py` 通过。
  - 内置样例 CLI dry-run 成功，生成 `临时文件\合同审查_dry_run.md`；终端中文回显在 Windows conda run 下仍可能乱码，但 UTF-8 报告文件内容正常。
- 最后更新: 2026-07-07

### T-027 收编知识库智能体为独立子项目

- 状态: Done
- 目标: 确认并补全外部导入的 `langchain_knowledge_base`，保持其作为可分离的独立智能体子项目，从自身目录运行，并明确使用本地 Chroma `PersistentClient` 持久化。
- 验收标准:
  - `src/agents/langchain_knowledge_base/` 保留独立 `pyproject.toml`、Dockerfile、README 和 `.env.example`。
  - 运行、测试、入库、问答和 Docker Compose 命令均以智能体目录为工作目录。
  - 默认不依赖外部 Chroma 服务，向量数据持久化到 `data/chroma/` 或 Compose 命名卷 `kb_chroma_data`。
  - 支持聊天模型和 embedding 模型分开配置，可用 DeepSeek 负责问答、百炼/DashScope `text-embedding-v4` 负责入库向量化。
  - 提供 `POST /v1/retrieval` 纯检索接口，并在同一个 API app 中提供 `GET /v1/models` 和 `POST /v1/chat/completions`。
  - 工作区登记表、运行手册、密钥说明和设计决策记录该智能体的独立子项目定位。
  - 单元测试、eval fixture 和 Ruff 通过；Docker 运行验证按本机 Docker 可用性单独执行。
- 执行计划:
  - 修正健康检查、环境模板和 Compose，使 Chroma 存储口径与 `PersistentClient` 一致。
  - 增加 retrieval-only API 和 OpenAI-compatible chat completions 入口。
  - 补全子项目 README 的数据目录、启停和重置说明。
  - 补充工作区级登记、运行文档、密钥说明和设计决策。
  - 运行独立子项目测试、eval 和 Ruff。
- 验证:
  - `python -m pytest -q` 通过，42 个测试通过。
  - `python -m evals.run` 通过，fixture 模式 3/3 通过。
  - `ruff check .` 通过。
  - `python -m compileall kb_api evals` 通过。
  - 当前环境未安装 `docker` 命令，未执行 Docker Compose runtime 验证；README 已记录 Compose 启停和数据卷行为。
- 最后更新: 2026-06-30

### T-026 将招标文件审查智能体封装为 OpenAI-compatible LLM

- 状态: Done
- 目标: 参考 `openai-compatible-llm-wrapper` skill，把已有 `tender-format-review` 暴露为 Dify/FastGPT 可调用的 OpenAI-compatible LLM 服务。
- 验收标准:
  - 保留原 CLI/API/MCP 入口不变，新增 `GET /v1/models` 和 `POST /v1/chat/completions`。
  - 模型 ID 稳定为 `tender-format-review-agent`，支持 `stream=false` 和 `stream=true`。
  - 普通模型探测提示返回 200 readiness 文本，不因缺少业务输入返回 400。
  - LLM prompt 可通过“招标文件”区块传入服务端 `.docx` 路径或 HTTP(S) `.docx` 链接。
  - 增加定向测试并同步 README、运行手册、登记表和设计决策。
- 执行计划:
  - 复用原 `review_tender_format` 服务层，新增薄的 OpenAI-compatible FastAPI app。
  - 补充 prompt 解析、SSE 输出和远程 `.docx` 临时下载。
  - 添加 LLM wrapper 测试并运行定向 pytest、ruff。
  - 更新相关文档和任务状态。
- 验证:
  - `python -m pytest tests\agents\test_tender_format_review_llm.py -q` 通过，8 个测试覆盖模型列表、非流式 dry-run、模型探测 readiness、流式 readiness、`thinking=false` 回退、FastGPT JSON 数组解析、临时 MinIO 传输映射和流式 dry-run。
  - `ruff check src\agents\tender_format_review\openai_compatible_api.py tests\agents\test_tender_format_review_llm.py` 通过。
- 最后更新: 2026-06-25

### T-025 沉淀 OpenAI-compatible LLM 包装 Skill

- 状态: Done
- 目标: 总结 `batch-resume-review-llm` 接入 FastGPT 的经验，形成可复用 skill，并增强 `langchain-agent-builder` 使后续智能体可选择构建 OpenAI-compatible LLM 入口。
- 验收标准:
  - `.codex/skills/openai-compatible-llm-wrapper/` 包含可触发的 `SKILL.md` 和 `agents/openai.yaml`。
  - Skill 覆盖接口契约、流式 SSE、Dify/FastGPT 接入、文件链接数组提示词结构和常见排障。
  - `langchain-agent-builder` 增加 OpenAI-compatible wrapper 选型与最小实现要求。
  - Skill 基础校验通过。
- 执行计划:
  - 整理本次 FastGPT 接入的成功路径和踩坑点。
  - 完善 `openai-compatible-llm-wrapper` skill。
  - 更新 `langchain-agent-builder` 的工作流和结构建议。
  - 运行 skill 校验。
- 验证:
  - `quick_validate.py .codex/skills/openai-compatible-llm-wrapper` 通过，输出 `Skill is valid!`。
- 最后更新: 2026-06-25

### T-024 创建批量简历 OpenAI-compatible 流式适配智能体

- 状态: Done
- 目标: 复制 `batch-resume-review` 为 `batch_resume_review_llm`，保留原智能体不变，并新增面向 Dify/FastGPT 自定义 LLM 节点的 OpenAI-compatible 流式接口。
- 验收标准:
  - 新目录 `src/agents/batch_resume_review_llm/` 可独立导入和运行，不依赖修改原 `batch_resume_review`。
  - 提供 `GET /v1/models` 和 `POST /v1/chat/completions`，模型 ID 为 `batch-resume-review-agent`。
  - `stream=false` 返回 OpenAI-compatible Chat Completions JSON，`stream=true` 返回 SSE chunk 和 `[DONE]`。
  - 同步 REST、MCP 能力在新智能体内保留，端口沿用 8006 和 8005。
  - 更新智能体 README、登记表、运行手册和设计决策。
- 执行计划:
  - 复制原批量简历智能体源码、规则和参考资料。
  - 在新包内调整服务命名、manifest 和 User-Agent。
  - 新增 OpenAI-compatible FastAPI 入口、消息解析和 SSE 输出。
  - 增加定向测试并运行原智能体回归。
- 验证:
  - `python -m pytest tests\agents\test_batch_resume_review_llm.py -q` 通过，3 个测试覆盖模型列表、非流式 dry-run 和流式 SSE dry-run。
  - `python -m pytest tests\agents\test_batch_resume_review.py -q` 通过，26 个原批量简历智能体回归测试通过。
  - `ruff check src\agents\batch_resume_review_llm tests\agents\test_batch_resume_review_llm.py` 通过。
- 最后更新: 2026-06-25

### T-023 扩展批量简历多格式解析与百炼 OCR

- 状态: Done
- 目标: 让 `batch-resume-review` 统一接受 PDF、DOC、DOCX、MD、TXT 简历，并在 PDF 或图片型 Office 文档缺少可用文本时使用 `DASHSCOPE_API_KEY` 调用百炼 OCR。
- 验收标准:
  - 本地路径、HTTP(S) URL 与 MCP 上传均接受 `.pdf`、`.doc`、`.docx`、`.md`、`.txt`。
  - DOC/DOCX 可提取正文；PDF/DOC/DOCX 无可审查文本时自动进入 OCR，文本型文件不产生 OCR 调用。
  - OCR 配置仅读取环境变量，缺少密钥或 OCR 调用失败时保留单候选人失败隔离并给出可诊断错误。
  - 增加解析/OCR 单元测试，定向 pytest 与 Ruff 通过，并同步 README、运行手册、登记表、密钥说明和设计决策。
- 执行计划:
  - 核对现有 loader、CLI/API/MCP 输入契约及百炼 OCR 官方接口。
  - 在 loader 边界增加 DOC 解析、文本质量判断和可替换的百炼 OCR 客户端。
  - 扩充测试夹具与入口文件类型校验，更新依赖和文档。
  - 运行定向测试、全部智能体回归和 Ruff。
- 验证:
  - `python -m pytest tests\agents\test_batch_resume_review.py -q` 通过，26 个测试通过；覆盖五种扩展名、DOC 转换、文本 DOCX 不触发 OCR、图片 DOCX OCR、扫描 PDF 分页 OCR、缺少密钥和 MCP MD 上传。
  - `python -m pytest tests\agents -q` 通过，47 个智能体测试通过。
  - `ruff check src\agents\batch_resume_review tests\agents\test_batch_resume_review.py` 通过。
  - 使用无敏感信息的合成简历图片真实调用百炼 `qwen3.5-ocr` 成功，正确提取姓名、技能和学历。
  - 已安装 PyMuPDF 到 `langchain` 环境，并生成 `dist/batch-resume-review-agent-0.4.0.zip`；ZIP 包含 OCR、DOC 转换模块和更新后的独立运行文档。
- 最后更新: 2026-06-24

### T-022 支持批量简历 API 读取 MinIO 预签名 URL

- 状态: Done
- 目标: 让 `batch-resume-review` 的 `resume_paths` 同时接受服务端本地路径和 FastGPT/MinIO 提供的 HTTP(S) 预签名文件 URL。
- 验收标准:
  - `POST /review` 可从 HTTP(S) URL 读取 DOCX、文本型 PDF、TXT 和 FastGPT 生成的 Markdown 文件。
  - URL 文件名能正确进行百分号解码，查询签名不进入报告、文件名或错误信息。
  - 远程读取具有超时、单文件大小上限、扩展名检查和可选主机白名单。
  - 单份远程文件读取失败仍按现有批处理语义进入该候选人的复核项，不中断其他候选人。
  - 定向 pytest、Ruff 和 API dry-run 验证通过，并同步 API/独立包文档。
- 执行计划:
  - 在简历 loader 中增加受限 HTTP(S) 字节流读取和安全文件名解析。
  - 调整图输入节点保留远程原始文件名，补充 API 与 loader 测试。
  - 更新智能体 README、独立包说明、运行手册、登记表和设计决策。
- 验证:
  - `python -m pytest tests\agents\test_batch_resume_review.py -q` 通过，17 个测试通过；覆盖预签名 URL、中文百分号文件名、签名脱敏、单文件失败隔离、大小上限和主机白名单。
  - `python -m pytest tests\agents -q` 通过，38 个智能体测试通过。
  - `ruff check src\agents\batch_resume_review tests\agents\test_batch_resume_review.py` 通过。
  - 已生成 `dist/batch-resume-review-agent-0.3.0.zip`。
  - 2026-06-24 实机复核发现：MinIO 在 Windows `127.0.0.1:9000` 可用，但预签名 URL 使用本机 WLAN 地址 `10.71.2.94:9000`，该地址 TCP 不可达；追加保留签名 Host 的 localhost 传输回退。
  - localhost 回退测试通过；真实 MinIO 健康端点使用 `10.71.2.94:9000` Host、经 `127.0.0.1:9000` 连接返回 HTTP 200。
  - 修复后定向测试 18 个、全部智能体测试 39 个通过，Ruff 通过；已重新生成 0.3.0 独立包。
  - 后续响应已从网络错误变为 MinIO HTTP 404；新增安全提取 MinIO XML 错误码和 Request ID。定向测试 19 个、全部智能体测试 40 个通过，详见问题日志。
  - 确认 FastGPT MinIO 实际发布为宿主机 9002；新增可配置的签名地址/传输地址分离，`.env.local` 使用 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002`。定向测试 20 个与 Ruff 通过，并在智能体 README、源码 docstring、决策和问题日志中记录兼容层及删除条件。
- 最后更新: 2026-06-24

### T-021 创建 WSL/Docker 访问 Windows API 中继技能

- 状态: Done
- 目标: 将 Windows API 经 WSL `socat` 中继给 Docker/FastGPT 容器的已验证排障方法沉淀为工作空间技能。
- 验收标准:
  - 在 `.codex/skills/connect-wsl-docker-to-windows-api/` 下存在规范的 `SKILL.md` 和 `agents/openai.yaml`。
  - 技能能区分 Windows、WSL、Docker 容器三个网络命名空间，并避免把物理默认网关误认为 Windows 宿主机。
  - 记录经 Docker bridge 地址监听、转发到 WSL `127.0.0.1` 的 `socat` 方法和验证命令。
  - 明确 `NO_PROXY` 仅在实际存在代理干扰时才需要调整，本次验证无需修改。
  - 通过 skill 基础校验。
- 执行计划:
  - 用 `skill-creator` 初始化工作空间技能。
  - 编写诊断、临时中继、验证、持久化与清理流程。
  - 运行 `quick_validate.py` 并复核生成文件。
- 验证:
  - `quick_validate.py .codex/skills/connect-wsl-docker-to-windows-api` 通过，输出 `Skill is valid!`。
  - 技能记录了本次已验证路径：Windows API `127.0.0.1:8006` → WSL `socat` → Docker bridge `172.24.0.1:18006` → FastGPT 容器。
  - `agents/openai.yaml` 已生成且无编码乱码；本技能未登记到智能体注册表。
- 最后更新: 2026-06-23

### T-020 补充批量简历智能体 API 调用文档

- 状态: Done
- 目标: 在 `batch-resume-review` README 中补充可直接执行的 REST API 启动、请求与响应说明。
- 验收标准:
  - 说明 API 服务启动、健康检查和交互式接口文档地址。
  - 提供使用内置测试夹具的 `POST /review` PowerShell dry-run 示例。
  - 说明请求字段、路径语义、主要响应字段和常见错误状态。
- 执行计划:
  - 对照 `api.py`、服务层和 API 测试核实接口契约。
  - 扩充智能体 README 的 API 章节。
  - 运行文档示例对应的最小 API 测试。
- 验证:
  - `D:\\ProgramData\\miniforge3\\Library\\bin\\conda.bat run -n langchain python -m pytest tests\\agents\\test_batch_resume_review.py -q` 通过，14 个测试通过。
  - README 示例与 `BatchResumeReviewRequest`、`BatchResumeReviewResponse` 及服务层路径语义逐项核对一致。
- 最后更新: 2026-06-23

### T-019 将批量简历智能体封装为可独立分发包

- 状态: Done
- 目标: 让 `batch-resume-review` 内置全部代码、审查规则和参考资料，可脱离当前工作区安装运行，并沉淀通用智能体打包方法。
- 验收标准:
  - 智能体包内不再导入 `src.agents.resume_review` 或 `src.reference_data`。
  - 简历解析、分块、安全检测、高校名单和学制资料全部封装在智能体目录。
  - 存在可复用的独立打包脚本、包清单、依赖和环境变量模板。
  - 独立包说明覆盖安装、CLI、API、stdio/HTTP MCP 配置、请求和响应字段。
  - 生成 ZIP，并在隔离目录验证导入、dry-run 和 MCP in-process 调用。
- 执行计划:
  - 复制并改造跨包依赖，调整运行路径。
  - 创建通用打包器和独立项目元数据。
  - 完善 MCP 文档与调用示例。
  - 运行测试、构建 ZIP 和隔离验证。
- 完成记录:
  - 批量智能体已内置简历解析、分块、安全检测和高校参考资料，源码不再导入工作区其他 `src` 包。
  - 新增清单驱动的 `scripts/package_agent_standalone.py`、独立安装模板、MCP 配置和 Python 调用示例。
  - 生成 `dist/batch-resume-review-agent-0.2.0.zip`，内含 SHA-256 文件清单。
  - 定向及隔离测试 18 项通过；全部智能体测试 35 项通过；Ruff 检查通过。
  - 隔离测试已在解压目录仅使用包内 `src` 完成 dry-run 和 FastMCP in-process 调用。
- 最后更新: 2026-06-23

### T-018 调整简历筛除、评分与复核语义

- 状态: Done
- 目标: 强制筛除提示词注入，避免技能熟练度误作硬筛，补充姓名、学制和特殊高校口径，并让待复核候选人参与排名。
- 验收标准:
  - 提示词注入由确定性代码强制筛除且不参与排名。
  - 学历仅在 JD 明确最低要求时硬筛；技能熟练度只影响评分。
  - 985/211、双一流和特殊科研院校作为教育背景加分优势。
  - 报告显示简历原文姓名和文件名。
  - 待复核候选人有分数时参与排名，并在附加复核项中重复显示。
- 验证:
  - 批量智能体 14 个测试通过，单份智能体 12 个测试通过。
  - 全部智能体和高校参考数据回归 38 个测试通过，Ruff 检查通过。
  - 三份内置样例 dry-run 成功生成 `临时文件\批量简历审查_规则调整_dry_run.md`。
- 最后更新: 2026-06-22

### T-017 建立高校层次与世界排名审查参照

- 状态: Done
- 目标: 整理 985/211、带年份双一流、一本及世界排名动态参照，并由两个简历智能体默认加载。
- 验证: 985 为 39、211 为 112、2022 第二轮双一流为 147；高校参考数据测试已纳入 38 个全体回归测试。
- 最后更新: 2026-06-22

### T-016 创建批量简历审查与排序智能体

- 状态: Done
- 目标: 创建 `batch-resume-review` 智能体，一次接收多份简历，按统一岗位要求完成审查、硬条件筛除、合格候选人评分排序和批量汇总。
- 验收标准:
  - 在 `src/agents/batch_resume_review/` 下存在独立可运行入口和统一审查规则 Markdown。
  - 支持多份 DOCX、文本型 PDF、TXT 简历；Markdown 仅作为本地测试夹具。
  - 每份简历独立审查并保留候选人、文件和证据编号，单份失败不阻断整个批次。
  - 明确不满足硬性筛选条件的候选人给出筛除理由且不参与排名；证据不足者进入待人工确认且不参与排名。
  - 仅对通过筛选者使用统一量表评分并稳定排序。
  - CLI、API、MCP 共用服务层和 LangGraph 工作流；MCP 接收多份简历 base64 和岗位要求文本。
  - 覆盖批量 dry-run、筛除隔离、排序、API 和 MCP 的最小测试。
- 执行计划:
  - 创建统一审查规则、状态模型和提示词。
  - 实现多候选人分块并行审查、决策、筛除、排序和报告汇总。
  - 实现 CLI、API、MCP 入口和批量测试样例。
  - 更新智能体登记、运行手册、环境模板和设计决策。
  - 运行 pytest、ruff 和 CLI dry-run。
- 验证:
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest tests\agents\test_batch_resume_review.py -q` 通过，9 个测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest tests\agents -q` 通过，30 个智能体测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain ruff check src\agents\batch_resume_review tests\agents\test_batch_resume_review.py` 通过。
  - 三份内置 Markdown 测试夹具 CLI dry-run 成功，生成 `临时文件\批量简历审查_dry_run.md`，报告确认输入 3 份且只有通过硬条件筛选者可参与排序。
- 最后更新: 2026-06-22

### T-015 创建简历审查智能体

- 状态: Done
- 目标: 创建 `resume-review` 人力简历审查智能体，支持 DOCX/PDF/TXT 简历，输出初筛质量、合规背调前置和岗位匹配评分报告，并提供 CLI/API/MCP 入口。
- 验收标准:
  - 在 `src/agents/resume_review/` 下存在可运行入口和审查事项 Markdown。
  - 支持 DOCX、文本型 PDF、TXT 解析；第一版不支持扫描件 OCR。
  - 审查事项按基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配拆分，并在正式模型调用时按维度并行检查。
  - 岗位 JD 可选；未提供 JD 时明确“未提供 JD，岗位匹配未评分”。
  - CLI、API、MCP 共用 `service.py` 和 LangGraph 工作流。
  - Markdown 仅作为本地测试夹具；MCP 接收 DOCX/PDF/TXT 简历 base64 和岗位要求文本。
  - 覆盖 loader、chunking、graph dry-run、service、API 和 MCP 的最小测试。
- 执行计划:
  - 创建简历审查事项和智能体源码。
  - 补充测试和 dry-run 路径。
  - 更新智能体登记表、运行文档、环境模板和依赖说明。
  - 运行最小必要验证。
- 验证:
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest tests\agents\test_resume_review.py -q` 通过，12 个测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain ruff check src\agents\resume_review tests\agents\test_resume_review.py` 通过。
  - MCP 测试确认可接收 TXT 简历 base64 和岗位要求文本，并拒绝仅用于本地测试的 Markdown 上传。
  - 使用两份 Markdown 测试夹具调用 `deepseek-v4-flash`，未使用 dry-run，已生成 `临时文件\简历审查_人工智能开发工程师_deepseek-v4-flash.md`；报告断言确认包含注入识别、学历重叠、岗位评分且无 dry-run 标记。
- 最后更新: 2026-06-22

### T-014 补充广西投资集团采购管理办法审查依据

- 状态: Done
- 目标: 将《广西投资集团有限公司采购管理办法》整理为适合 `tender-format-review` 智能体使用的审查依据，并确保 MCP/API/CLI 默认审查时能够实际使用审查规则。
- 验收标准:
  - PDF 已解析并沉淀为 Markdown 审查依据。
  - 审查依据覆盖采购方式、必须招标限额、集中采购层级、电子采购平台、程序时限、非招标采购、合同签订和付款归档等关键规则。
  - 默认审查指南会加载补充依据，并注入分块审查 prompt。
  - 最小测试和 ruff 检查通过。
- 执行计划:
  - 阅读工作空间与智能体文档。
  - 抽取 PDF 文本并整理为审查依据 Markdown。
  - 调整审查指南加载与 prompt 使用方式。
  - 运行最小必要验证。
- 验证:
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest tests\agents\test_tender_format_review.py -q` 通过，9 个测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain ruff check src\agents\tender_format_review tests\agents\test_tender_format_review.py` 通过。
- 最后更新: 2026-06-18

### T-013 收敛 tender-format-review MCP 调用接口

- 状态: Done
- 目标: 将 MCP tool 调整为面向远程调用方的文件上传式接口，隐藏服务端内部路径、模型和输出细节。
- 验收标准:
  - MCP tool 只接收 `docx_base64`、`docx_filename` 和 `dry_run`。
  - 客户端可把本机 docx 内容发送给 MCP 服务端审查。
  - MCP 不要求客户端填写 `review_guide_path`、`catalog_path`、`provider`、`model` 或 `output_path`。
  - 审查报告通过 tool 返回，由调用方示例保存到本机文件。
- 执行计划:
  - 收敛 `mcp_server.py` tool 参数和返回字段。
  - 更新 MCP 调用脚本和测试。
  - 重写智能体 README 的 MCP 调用说明。
  - 运行最小必要验证。
- 验证:
  - `C:\Users\Lenovo\.conda\envs\langchain\python.exe -m pytest tests\agents\test_tender_format_review.py -q` 通过，8 个测试通过。
  - `C:\Users\Lenovo\.conda\envs\langchain\python.exe -m ruff check src\agents\tender_format_review\mcp_server.py src\agents\tender_format_review\prompts.py src\agents\tender_format_review\graph.py scripts\call_tender_format_review_mcp.py tests\agents\test_tender_format_review.py` 通过。
  - `C:\Users\Lenovo\.conda\envs\langchain\python.exe scripts\call_tender_format_review_mcp.py --transport stdio --docx-path .\临时文件\仅包含一行文字的文件.docx --save-report .\临时文件\mcp_upload_dry_run_report.md` 通过，报告已保存。
- 最后更新: 2026-06-18

### T-012 将招标文件格式审查智能体封装成 MCP

- 状态: Done
- 目标: 将 `src/agents/tender_format_review/` 封装成可被 MCP client 调用的 stdio MCP server，并沉淀通用 MCP 封装指引。
- 验收标准:
  - 存在可启动的 MCP server 入口。
  - MCP tool 复用 `service.py`，与 CLI/API 共用同一个 LangGraph 工作流。
  - 可通过 MCP client 调用 `./临时文件/仅包含一行文字的文件.docx` dry-run。
  - 文档记录 MCP 启动、tool 参数、客户端配置示例和后续智能体封装指引。
- 执行计划:
  - 新增 `mcp_server.py` 和 `review_tender_format` MCP tool。
  - 补充 FastMCP in-process dry-run 测试。
  - 更新运行文档、智能体登记表、环境依赖和 MCP 封装指引。
  - 运行最小必要验证。
- 验证:
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest tests\agents\test_tender_format_review.py -q` 通过，8 个测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain python -m pytest -q` 通过，8 个测试通过。
  - `D:\ProgramData\miniforge3\Library\bin\conda.bat run -n langchain ruff check .` 通过。
  - 测试已覆盖 FastMCP in-process 调用和真实 stdio 子进程调用，均使用 `./临时文件/仅包含一行文字的文件.docx` dry-run。
  - 已补充 stdio/HTTP MCP 启动差异说明和 `scripts\call_tender_format_review_mcp.py` 调用脚本；stdio 与 HTTP 调用脚本均验证返回 `chunk_count=1`。
- 最后更新: 2026-06-17

### T-011 将招标文件格式审查智能体封装成 API

- 状态: Done
- 目标: 将 `src/agents/tender_format_review/` 封装成可供前端和编排工作流节点调用的 API，并沉淀通用 API 封装指引。
- 验收标准:
  - 存在可启动的 FastAPI 入口。
  - CLI 和 API 复用同一个服务层调用，避免逻辑分叉。
  - 可用 `./临时文件/仅包含一行文字的文件.docx` 执行 dry-run 测试。
  - 文档记录 API 启动、调用方式和后续智能体封装指引。
- 执行计划:
  - 抽取 `review_tender_format` 服务函数。
  - 新增 FastAPI 请求/响应模型和 `/review` 接口。
  - 补充服务层、API dry-run 测试。
  - 更新运行文档、智能体登记表和 API 封装指引。
  - 运行最小必要验证。
- 验证:
  - `$env:PYTHONIOENCODING='utf-8'; conda run -n langchain python -m pytest tests\agents\test_tender_format_review.py -q` 通过，6 个测试通过。
  - `$env:PYTHONIOENCODING='utf-8'; conda run -n langchain python -m pytest -q` 通过，6 个测试通过。
  - `$env:PYTHONIOENCODING='utf-8'; conda run -n langchain ruff check .` 通过。
  - 启动 `uvicorn src.agents.tender_format_review.api:app --host 127.0.0.1 --port 8001` 后，对 `POST /review` 使用 `./临时文件/仅包含一行文字的文件.docx` dry-run，返回 `chunk_count=1`。
- 最后更新: 2026-06-17

### T-001 建立 Agent 可读工作空间框架

- 状态: Done
- 目标: 创建让 Agent 快速理解工作区的入口文档、目录规范、任务台账和问题记录。
- 验收标准:
  - 根目录存在 `README.md` 和 `AGENTS.md`。
  - 存在任务台账、环境说明、运行调试说明、密钥说明和问题日志。
  - 目录结构包含 `.agents/`、`docs/`、`src/`、`tests/`、`secrets/`。
- 验证: 已创建对应目录和文档。

### T-002 整理现有 API key

- 状态: Done
- 目标: 将未整理 key 转成开发可用的环境变量文件，并归档原始文件。
- 验收标准:
  - 根目录存在 `.env.local`。
  - 根目录存在 `.env.example`。
  - 原始 key 文件归档到 `secrets/raw/unorganized-api-keys/`。
  - 文档说明变量名但不泄露明文 key。
- 验证: 已生成 `.env.local`，并更新 `docs/operations/SECRETS.md`。

### T-003 编写 LangChain / LangGraph conda 环境说明

- 状态: Done
- 目标: 提供可复用的 conda 环境创建和验证说明。
- 验收标准:
  - 存在 `environment.yml`。
  - 存在 `docs/development/CONDA_LANGCHAIN_ENV.md`。
  - 文档说明创建、更新、验证命令。
- 验证: 已创建环境文件和文档。

### T-004 确认 conda 环境 `langchain` 已就绪

- 状态: Done
- 目标: 将用户已创建 conda 环境 `langchain` 的状态同步到工作空间文档。
- 验收标准:
  - README 说明环境已创建。
  - 环境和运行文档默认使用 `conda activate langchain`。
  - 交接记录说明后续无需重复创建环境。
- 验证: 已更新当前状态和交接记录。

### T-005 建立多智能体登记机制

- 状态: Done
- 目标: 支持本工作空间承载多个智能体，并能快速查找每个智能体的用途、路径、入口和状态。
- 验收标准:
  - 存在 `docs/workspace/AGENT_REGISTRY.md`。
  - 工作空间纲领说明新增智能体登记规则。
  - README 指向智能体登记表。
- 验证: 已创建登记表并更新相关文档。

## Backlog

### T-009 创建招标文件格式审查智能体

- 状态: Done
- 目标: 使用 LangChain / LangGraph 创建可接收 docx 招标文件的格式审查智能体，明确超长文档分块审查工作流、模型上下文约束、提示词和输出报告。
- 验收标准:
  - 在 `src/agents/tender_format_review/` 下存在可运行入口。
  - 能从 docx 提取文本和表格，按章节/长度拆分后审查。
  - 明确 DeepSeek、Qwen 等模型上下文不足或虽可容纳但不宜整篇一次审查时的处理策略。
  - 提供大模型节点提示词和可复用配置。
  - 更新智能体登记表和运行调试文档。
- 执行计划:
  - 阅读工作空间文档和招标审查事项。
  - 实现 docx 解析、分块、LangGraph 节点、CLI 和 dry-run 模式。
  - 补充 README、登记表、运行文档和最小测试。
- 验证:
  - `$env:PYTHONIOENCODING='utf-8'; conda run -n langchain python -m pytest` 通过，3 个测试通过。
  - `$env:PYTHONIOENCODING='utf-8'; conda run -n langchain ruff check .` 通过。
- 最后更新: 2026-06-16

### T-010 创建 LangChain 智能体创建 skill

- 状态: Done
- 目标: 将本次创建智能体的可复用经验沉淀为 `langchain-agent-builder` skill，方便后续按工作空间规范创建新的 LangChain / LangGraph 智能体。
- 验收标准:
  - 存在 `.codex/skills/langchain-agent-builder/SKILL.md`。
  - skill 覆盖任务登记、目录约定、模型配置、图节点拆分、提示词、测试和文档同步。
  - 通过 skill 基础校验。
- 执行计划:
  - 用 skill-creator 模板初始化 skill。
  - 根据本次招标审查智能体实现经验编写精简说明。
  - 运行 quick_validate 校验。
- 验证:
  - `conda run -n langchain python C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py .codex\skills\langchain-agent-builder` 通过。
- 最后更新: 2026-06-16

### T-006 添加最小可运行 LangGraph Agent 示例

- 状态: Backlog
- 目标: 在 `src/agents/` 中添加一个可运行的最小图示例。
- 验收标准:
  - 可以通过命令行调用。
  - 能读取 `.env.local`。
  - 有最小测试覆盖。

### T-007 建立模型配置与 provider 适配层

- 状态: Backlog
- 目标: 封装 DeepSeek、DashScope 和后续模型 provider 的配置加载。
- 验收标准:
  - 不在业务逻辑中直接读取环境变量。
  - 缺少 key 时给出清晰错误。

### T-008 建立 Agent 调试样例和 LangSmith tracing 指南

- 状态: Backlog
- 目标: 增加 tracing 开关和示例运行记录。
- 验收标准:
  - 可以通过环境变量控制 tracing。
  - 文档说明如何定位节点输入输出。
