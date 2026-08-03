# Problem Log

### 2026-07-30 - 全仓公文 golden 测试缺少本地输入文件

- 状态: Open
- 影响: 部门知识库改造的全仓验证有两个公文 golden用例无法执行，但其余201项测试
  通过；部门知识库、知识库核心及打包聚焦46项全部通过。
- 现象: 测试环境缺少 `临时文件/公文格式化配置/公文格式规范.docx` 及采购请示原始
  输入文件，对应用例在读取 fixture时失败，尚未进入业务断言。
- 结论: 这是本地测试资产缺失，不是本次部门知识库代码失败；未复制或臆造输入文件。
- 下一步: 恢复原始 golden输入后补跑完整公文格式化测试。
- 关联任务: T-052

### 2026-07-30 - 多扫描文档保存长时间无进度并留下未提交快照

- 状态: Fixed
- 影响: 三文档保存可能超过 AI 平台 180 秒流式读取等待；失败前原件和本地文档已经
  写入，但 Chroma 与 manifest 未完成，且旧实现有先重置当前索引的风险。
- 现象: 用户最后才看到“已锁定知识空间”和“部门知识库服务暂时不可用”；现场三份
  原件均在 MinIO 和 documents 中，其中一份 48 页全部需要 OCR，而 Chroma 为空、
  manifest 不存在。
- 结论: 保存改为后台事件队列加阶段进度/心跳；文档与 Chroma 在版本目录完整构建，
  校验后原子切换 manifest 指针。失败日志带请求 ID和阶段且移除签名查询参数。
- 关联任务: T-049

### 2026-07-28 - 当前验证环境缺少仓库声明的 langchain 环境、Ruff 与 Docker CLI

- 状态: Open
- 影响: `comfyui-video-generation-agent` 可以完成定向测试、编译、配置结构和远程 ComfyUI连通性验证，但不能在当前会话执行 Ruff或原生 `docker compose config`。
- 现象: 文档中的 `C:\Users\Lenovo\.conda\envs\langchain\python.exe` 不存在；当前默认 Python没有 pytest；可用 `D:\miniforge\envs\testenv\python.exe` 有测试依赖但没有 Ruff；PowerShell没有 Docker，WSL Ubuntu也报告 `docker: command not found`。
- 已尝试: 使用 testenv完成19项定向回归和136项全仓测试；用 PyYAML解析 Compose并断言只有 gateway发布端口；用 Agent自身 httpx客户端确认远程 ComfyUI健康。
- 下一步: 恢复文档声明的 langchain conda环境或按 `environment.yml` 重建，并在具备 Docker CLI的部署环境补跑 Ruff与 `docker compose config --quiet`。
- 关联任务: T-043

用于记录开发、环境、依赖、模型调用或 Agent 行为中的问题。不要记录真实密钥。

## 模板

```text
### YYYY-MM-DD - 简短标题

- 状态: Open / Investigating / Fixed / Won't Fix
- 影响:
- 现象:
- 复现步骤:
- 初步判断:
- 已尝试:
- 结论:
- 关联任务:
```

## 记录

### 2026-07-27 - PowerShell 经 WSL 写远端 env 时换行被转义

- 状态: Fixed
- 影响: 首次生成 `/opt/agent-workspace/.env` 时，两项 Compose 插值变量被写成同一
  行，镜像标签包含了字面量 `nAGENT_GATEWAY_PORT=10085n`。
- 现象: `docker compose config --images` 输出异常镜像名；服务尚未启动。
- 初步判断: PowerShell、`wsl.exe`、Bash 和远端 SSH 多层解析消耗了 `\n` 转义。
- 已尝试: 改成两个独立 `echo` 写入动作，再次执行 `docker compose config --quiet`
  和 `docker compose config --images`。
- 结论: 镜像标签恢复为 `agent-workspace:20260727-1243-fcbbba248cd8`，端口变量独立为
  `10085`，之后才执行正式启动。跨 Windows/WSL/SSH 写多行配置时不要依赖嵌套
  `printf` 转义，应逐行写入或上传已校验文件。
- 关联任务: T-042

### 2026-07-24 - 旧批量简历测试引用已移除包

- 状态: Fixed
- 影响: 直接运行 `pytest tests` 时，`tests/agents/test_batch_resume_review.py` 在收集阶段无法导入 `src.agents.batch_resume_review`。
- 现象: 当前源码只有 canonical `src/agents/batch_resume_review_llm/`，但旧测试仍导入已不存在的兼容包路径。
- 复现步骤: 运行 `python -m pytest tests -q`。
- 初步判断: T-036/T-038记录要求旧包保留薄兼容转发，但当前工作树没有该目录；与 T-040 图片智能体实现无关。
- 已尝试: 排除该既有测试后运行全部其余测试，136项通过；全仓 Ruff通过。
- 结论: 用户确认旧包已正式移除；已删除只覆盖该包的 `tests/agents/test_batch_resume_review.py`。其余136项测试完整收集并通过。
- 关联任务: T-036 / T-038 / T-040

### 2026-07-14 - 中文 Windows 挂载路径导致 Docker BuildKit 会话头失败

- 状态: Fixed
- 影响: 在 WSL Ubuntu 从当前 `/mnt/e/.../--创建智能体工作空间--` 路径执行 Compose BuildKit 构建时，无法创建统一 Linux 镜像。
- 现象: BuildKit 报 `x-docker-expose-session-sharedkey` 包含 non-printable ASCII character。
- 复现步骤: 在当前 WSL 项目目录运行 `docker compose build gateway`。
- 初步判断: Windows 挂载路径中的中文进入 BuildKit 会话共享键 HTTP 头，违反 ASCII 头值约束；Dockerfile 本身无关。
- 已尝试: 设置 `DOCKER_BUILDKIT=0` 使用传统构建器，统一镜像构建成功；Compose 配置、启动和故障隔离验收均通过。
- 结论: 当前路径使用 `DOCKER_BUILDKIT=0 docker compose build gateway`。项目迁移到纯 ASCII Linux 路径后再恢复 BuildKit。
- 关联任务: T-036

### 2026-07-14 - 分离 WSL 命令期间 Docker 引擎休眠干扰验收

- 状态: Fixed
- 影响: 多次独立调用 WSL 命令时，Docker 引擎曾短暂重启，使全部容器同时不可达，容易误判为 worker 故障隔离失败。
- 现象: 命令间隔后网关和 worker 同时暂时失联，而不是只有被停止的 worker 不可用。
- 初步判断: 当前 WSL/Docker 生命周期会在无持续会话时休眠或重启。
- 已尝试: 在同一个持续 WSL shell 中执行 worker 停止、模型列表检查、其他模型调用和恢复检查。
- 结论: 持续会话验收通过：停止 `contract-review` 后模型数从 6 降为 5，其他 worker 可调用，恢复后重新为 6。
- 关联任务: T-036

### 2026-06-25 - Tender LLM wrapper 读取 FastGPT MinIO 预签名 URL 需临时端口映射

- 状态: Fixed
- 影响: `tender-format-review` 的 OpenAI-compatible LLM 入口从 FastGPT prompt 中读取 `.docx` 预签名 URL 时，可能无法通过 URL 上的 `10.71.2.94:9000` 直接取到文件。
- 现象: FastGPT 提供的 MinIO URL Host 为 `10.71.2.94:9000`，但 Windows 本机实际访问该 FastGPT MinIO 实例需要走 `127.0.0.1:9002`。
- 复现步骤: 在 FastGPT LLM 节点提示词中传入 `http://10.71.2.94:9000/...docx?...X-Amz-Signature=...` 后调用 `tender-format-review-agent`。
- 初步判断: 这是当前本机 Docker/FastGPT/MinIO 发布端口与签名 Host 不一致导致的环境兼容问题。
- 已尝试: 在 `src/agents/tender_format_review/openai_compatible_api.py::_temporary_minio_transport_mapping` 中增加临时传输映射：实际 TCP 连接走 `127.0.0.1:9002`，HTTP `Host` 仍保持 `10.71.2.94:9000`，查询签名不改写。
- 结论: 2026-07-14 已删除智能体硬编码，改由共享附件模块的 `AGENT_REMOTE_TRANSPORT_OVERRIDES` 显式配置，仍保留原 Host 和 AWS V4 查询签名。
- 长期建议: 优先修正 FastGPT 的 MinIO 外部访问/签名地址，使预签名 URL 直接使用实际可达地址或统一反向代理域名；届时删除环境映射。
- 关联任务: T-026

### 2026-06-24 - Windows API 读取 FastGPT MinIO 预签名 URL 返回 404

- 状态: Investigating
- 影响: `batch-resume-review` 能接收 URL，但四份简历均未解析，无法进入模型评分。
- 现象: 初次为访问 `10.71.2.94:9000` 的 network error；增加本机 localhost 传输回退后变为 MinIO HTTP 404。
- 复现步骤: FastGPT 容器经 `172.24.0.1:18006` socat 中继调用 Windows `127.0.0.1:8006/review`，请求中的简历为 `http://10.71.2.94:9000/fastgpt-private/...` 预签名 URL。
- 初步判断: 容器到 Windows API 的 socat 中继工作正常；Windows 无法访问 Docker bridge `172.24.0.1:9000`，但 `127.0.0.1:9000` MinIO 健康检查正常。后续响应已确认四份文件均为 `NoSuchKey`。
- 已尝试: loader 对本机 HTTP 地址失败时经 localhost 连接并保留原始签名 Host；真实健康端点返回 200。新增安全解析 MinIO XML 错误码和 Request ID，且不回显查询签名。
- 结论: 进一步确认宿主机 9000 属于另一套 MinIO，FastGPT MinIO 实际发布为 `9002 -> 9000`，因此此前 localhost 同端口回退访问了错误实例并得到 `NoSuchKey`。新增 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002` 传输映射，保留签名 URL 的原始 Host。
- 长期建议: 当前映射属于兼容层。优先修正 FastGPT 的 MinIO 外部签名地址为实际发布端口 9002 或统一反向代理域名；新 URL 验证通过后删除兼容环境变量。智能体 README 和 loader docstring 已记录删除条件与签名约束。
- 关联任务: T-022

### 2026-06-17 - Codex 后台启动 HTTP MCP 时 conda run 和外部环境权限失败

- 状态: Fixed
- 影响: Agent 需要启动 `tender-format-review` 常驻 HTTP MCP 服务时，使用 `conda run` 或沙箱内直接导入外部 conda 环境包可能失败，导致 `http://127.0.0.1:8002/mcp` 未监听。
- 现象: 后台 `conda run -n langchain python -m src.agents.tender_format_review.mcp_server --transport http ...` 报 `Access is denied` 和找不到 `C:\Users\Lenovo\AppData\Local\Temp\__conda_tmp_*.txt`；沙箱内直接用环境 Python 导入 LangChain 时，可能因读取 `C:\Users\Lenovo\.conda\envs\langchain\Lib\site-packages` 权限不完整触发 `opentelemetry.context` 的 `StopIteration`。
- 复现步骤: 在 Codex 受限沙箱中用 `conda run` 后台启动 HTTP MCP，或不提升权限直接运行 `C:\Users\Lenovo\.conda\envs\langchain\python.exe -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp`。
- 初步判断: `conda run` 需要访问用户 Temp 目录；外部 conda 环境位于工作区之外，受限沙箱无法稳定读取全部包和入口点元数据。
- 已尝试: 改为在提升权限下直接调用 `C:\Users\Lenovo\.conda\envs\langchain\python.exe`，使用 `Start-Process -WindowStyle Hidden` 后台运行，并把 stdout/stderr 重定向到 `临时文件\tender_format_review_mcp.*.log`。
- 结论: 该方式已成功启动常驻 HTTP MCP，日志显示 `Uvicorn running on http://127.0.0.1:8002`；使用 `C:\Users\Lenovo\.conda\envs\langchain\python.exe scripts\call_tender_format_review_mcp.py --transport http --url http://127.0.0.1:8002/mcp` 验证通过，返回 tool `review_tender_format`、`dry_run=true`、`chunk_count=1`。
- 关联任务: T-012

### 2026-06-16 - Windows 下 conda run 输出编码异常

- 状态: Fixed
- 影响: `conda run -n langchain python -m pytest` 可能在中文路径或非 UTF-8 输出下触发 GBK 编码错误，导致测试输出异常。
- 现象: conda 报 `UnicodeEncodeError: 'gbk' codec can't encode character`。
- 复现步骤: 在 PowerShell 中直接运行 `conda run -n langchain python -m pytest`。
- 初步判断: conda 包装 stdout 时使用系统默认 GBK 编码，测试输出含无法编码字符。
- 已尝试: 设置 `$env:PYTHONIOENCODING='utf-8'` 后重跑。
- 结论: 使用 UTF-8 输出后测试正常通过。
- 关联任务: T-009 / T-010

### 2026-06-16 - `.env.local` 中模型 API key 为凭证标签而非真实 token

- 状态: Fixed
- 影响: `tender-format-review` 无法实际调用 DeepSeek 或 DashScope/Qwen，只能完成 docx 解析和 dry-run 分块。
- 现象: 调用 DeepSeek 时 httpx 构造 `Authorization` header 失败，报 `UnicodeEncodeError: 'ascii' codec can't encode characters`。
- 复现步骤: 运行 `python -m src.agents.tender_format_review review ... --provider deepseek`。
- 初步判断: `.env.local` 使用两行格式，第一行是 `变量名=凭证名称...`，下一行才是真实 `sk-...` token；加载器只读取了第一行。
- 已尝试: 已将 `.env.local` 规整为 `变量名=真实token` 的一行格式；已在 `llm.py` 增加提前校验，避免深层 traceback。
- 结论: 格式修复后 DeepSeek 正式审查命令已成功生成报告。
- 关联任务: T-009
# 2026-08-02 - 远端统一 MCP 发布版本落后于本机

- 状态: Open
- 现象: 服务器 `10085/mcp` 可以初始化，但 `official_document_format` 调用返回工具错误。
- 根因: 服务器运行镜像 `agent-workspace:git-b6e3741751d7` 的 `config/agent_gateway.json` 只登记旧的 `department-knowledge-base` MCP，`mcp_backends` 为空；服务器当前 Compose 也没有 `mcp-gateway` service。公文 worker 的共享 token 映射已配置且容器内 token/权限匹配，但旧网关无法发现或路由公文格式化工具。
- 处理: 本机 `8008/mcp` 已完成正确、错误和缺失 token 的端到端验证；远端已安全写入同 token 的 `AGENT_MCP_TOKENS_JSON` 并只重建公文 worker。待将当前统一 MCP、DOC/DOCX 和 URL 支持变更整理为可复盘提交/release 后，再按服务器发布流程升级并验证 `tools/list`。
- 注意: 不要直接把当前包含大量未提交修改的工作树覆盖发布到服务器。
