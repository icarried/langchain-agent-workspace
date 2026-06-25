# Task Board

## 使用规则

- 每个任务必须有状态、目标和验收标准。
- 开始前将状态改为 `In Progress`。
- 完成后写清验证方式，再改为 `Done`。
- 被阻塞时写清阻塞原因和下一步需要什么。

## 当前任务

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
