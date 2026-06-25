# Problem Log

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
