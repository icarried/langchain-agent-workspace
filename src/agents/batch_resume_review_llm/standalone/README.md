# Batch Resume Review LLM Agent - Standalone

本目录是一套可脱离原多智能体工作区安装运行的批量简历审查 LLM 适配器。它保留批量简历筛选、评分、排序和 MCP 能力，并额外提供 OpenAI-compatible `/v1/chat/completions` 流式接口，便于 Dify/FastGPT 作为自定义模型调用。

本说明只适用于已打包、脱离工作区运行的 ZIP，因此示例使用独立 `8006` 端口。工作区生产部署请不要使用该端口，统一改用 `http://<host>:8008/v1`、模型 `batch-resume-review-agent`，并参阅根目录 `docs/development/AGENT_GATEWAY.md`。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env.local
```

在 `.env.local` 中填写 `GPU_STACK_API_KEY` 和 `GPU_STACK_BASE_URL`。文本型 PDF 直接解析；
扫描 PDF页和图片型 DOCX默认调用 GPU Stack `paddleocr-vl-1.6`。正式筛选模型也默认复用
GPU Stack；真实密钥不要提交或发给客户端。

## OpenAI-compatible Server

```powershell
.\.venv\Scripts\python.exe -m uvicorn batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

- Base URL: `http://<host>:8006/v1`
- Model: `batch-resume-review-agent`
- Chat endpoint: `POST /v1/chat/completions`
- Models endpoint: `GET /v1/models`

提示词中使用：

```text
岗位要求：要求本科及以上学历，熟悉 Python。

简历文件：
http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...
```

## CLI

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review_llm review `
  .\resumes\candidate-a.pdf .\resumes\candidate-b.docx `
  --job-description .\job-description.txt `
  --output .\output\report.md
```

## REST API

```powershell
.\.venv\Scripts\python.exe -m uvicorn batch_resume_review_llm.api:app --host 127.0.0.1 --port 8006
```

REST 接口为 `GET /health` 和 `POST /review`。`resume_paths` 可使用服务端文件路径或 FastGPT/MinIO 的 HTTP(S) 预签名 URL。

## MCP Server

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review_llm.mcp_server
```

HTTP MCP:

```powershell
.\.venv\Scripts\python.exe -m batch_resume_review_llm.mcp_server `
  --transport http --host 127.0.0.1 --port 8005 --path /mcp
```

tool 名称：`review_resumes`。
