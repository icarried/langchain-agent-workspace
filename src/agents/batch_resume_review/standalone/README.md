# Batch Resume Review Agent - Standalone

本目录是一套可脱离原多智能体工作区安装运行的批量简历审查智能体。解析器、审查规则、提示词注入检测、高校名单、学制判断和 MCP 服务均已内置。

## 安装

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env.local
```

在 `.env.local` 中填写 `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`。真实密钥不要提交或发给 MCP 客户端。

## 文件解析与 OCR

文本型 PDF/DOCX 优先本地解析；无文本 PDF 页面和图片型 DOCX 自动调用百炼 `qwen3.5-ocr`。旧 DOC 先使用 Microsoft Word + pywin32（Windows）或 LibreOffice 转为 DOCX，Word 自动化会强制禁用宏。OCR 仅使用服务端 `DASHSCOPE_API_KEY`，页面图像会发送给百炼。

可用 `BATCH_RESUME_REVIEW_OCR_MODEL`、`BATCH_RESUME_REVIEW_OCR_BASE_URL`、`BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MAX_PAGES` 和 `BATCH_RESUME_REVIEW_MIN_TEXT_CHARS` 覆盖默认配置。
## CLI

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review review `
  .\resumes\candidate-a.pdf .\resumes\candidate-b.docx `
  --job-description .\job-description.txt `
  --output .\output\report.md `
  --dry-run
```

正式审查时去掉 `--dry-run`。注意：dry-run 只跳过筛选/评分模型；扫描件解析仍会调用百炼 OCR。

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn batch_resume_review.api:app --host 127.0.0.1 --port 8006
```

REST 接口为 `GET /health` 和 `POST /review`。`resume_paths` 可使用服务端文件路径或 FastGPT/MinIO 的 HTTP(S) 预签名 URL；远程读取默认限制为每份 10 MiB、30 秒。`job_description_text` 应传岗位要求正文，服务端文件路径应使用 `job_description_path`。

可通过环境变量 `BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS` 配置逗号分隔的 URL 主机白名单，通过 `BATCH_RESUME_REVIEW_MAX_REMOTE_FILE_BYTES` 和 `BATCH_RESUME_REVIEW_REMOTE_TIMEOUT_SECONDS` 覆盖大小与超时。签名查询参数不会进入报告、错误信息或响应的 `resume_paths`。

本机 WSL/Docker 场景中，若预签名 HTTP URL 使用本机网卡地址但 MinIO 仅能从 Windows localhost 访问，loader 会在首次网络连接失败后改走 `127.0.0.1`，并保留原始签名 `Host` 请求头。

若 Docker 发布端口与签名 URL 不同，设置 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT`，例如 `http://127.0.0.1:9002`。它只改变实际连接地址，不改变签名 URL 的 Host。

## MCP Server

### stdio

MCP 客户端按需启动服务，通常不需要手工常驻：

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review.mcp_server
```

客户端配置见 `mcp-config.example.json`。`command` 和 `cwd` 必须改为解压目录的绝对路径。macOS/Linux 将解释器路径改为 `<bundle>/.venv/bin/python`。

### HTTP

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review.mcp_server `
  --transport http --host 127.0.0.1 --port 8005 --path /mcp
```

连接地址为 `http://127.0.0.1:8005/mcp`。这是 MCP Streamable HTTP 端点，不是普通 REST `/review`。

## MCP Tool

tool 名称：`review_resumes`

请求：

```json
{
  "resumes": [
    {
      "filename": "candidate-a.pdf",
      "content_base64": "<base64 file bytes>"
    },
    {
      "filename": "candidate-b.docx",
      "content_base64": "<base64 file bytes>"
    }
  ],
  "job_description_text": "完整岗位要求文本",
  "dry_run": false
}
```

约束：

- 每批 1-100 份简历。
- 单文件最大 10 MiB。
- MCP 上传格式为 PDF、DOC、DOCX、MD、TXT；扫描 PDF 和图片型 Word 文件按需调用百炼 OCR。
- `filename` 必须唯一，服务端只使用安全文件名，不接受路径穿越。
- `job_description_text` 必填且不能为空。
- `dry_run=true` 只验证上传、解析和流程，不调用模型，也不会产生真实排名。

主要响应字段：

- `report`：完整 Markdown 报告。
- `candidate_count`：输入候选人数。
- `qualified_count`：进入排名的人数，包含有分数的待复核候选人。
- `excluded_count`：筛除人数。
- `pending_count`：附加复核人数；其中有分数者也会出现在 `ranking`。
- `ranking`：排名结果，包含姓名、文件名、分数、状态和名次。
- `excluded`：筛除结果及理由，与 `ranking` 互斥。
- `pending`：复核项，可与 `ranking` 重叠。
- `filenames`：本批上传的原始文件名。

模型、provider、密钥和审查规则由服务端管理，不暴露为 MCP tool 参数。

## MCP 调用示例

stdio dry-run：

```powershell
.\.venv\Scripts\python.exe .\mcp_client_example.py `
  .\resumes\candidate-a.txt .\resumes\candidate-b.pdf `
  --job-description .\job-description.txt `
  --save-report .\output\mcp-report.md
```

HTTP 正式调用：

```powershell
.\.venv\Scripts\python.exe .\mcp_client_example.py `
  .\resumes\candidate-a.txt .\resumes\candidate-b.pdf `
  --job-description .\job-description.txt `
  --transport http --url http://127.0.0.1:8005/mcp `
  --no-dry-run --save-report .\output\mcp-report.md
```

## 数据与安全

- 上传文件写入系统临时目录，调用结束后自动删除。
- API 远程文件在内存中受限读取，不落盘；API 应仅暴露给受信任的内网调用方，并建议配置 URL 主机白名单。
- 正式调用会把解析后的简历文本和岗位要求发送给配置的模型服务商。
- 内置高校和学制资料带来源及核对日期；更新时重新打包并保留旧包版本。
- 不在包内放置 `.env.local`、真实密钥、候选人简历或审查输出。
