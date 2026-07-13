# official-document-review

`official-document-review` 是根据 FastGPT 导出工作流“公文优化”的有效经验转化而来的 LangChain / LangGraph 智能体。它不照搬 FastGPT 的内网 HTTP 检测节点，而是保留“文件检测 -> 检测结果美化输出”的分层设计，在本工作区实现可测试、可本地运行的公文格式检查与优化建议。

## 能力范围

- 支持本地 DOCX、文本型 PDF、TXT、MD 公文解析。
- 对 DOCX 做 A4、页边距、标题和正文字体线索等基础版式检查。
- 对所有文本输入做标题、主送机关、成文日期、文种线索等结构检查。
- 输出问题清单、整改建议和可读 Markdown 报告。
- 支持 CLI、REST API 和 MCP；支持 `--dry-run`，不调用模型。

## CLI

```powershell
python -m src.agents.official_document_review review `
  src\agents\official_document_review\examples\示例通知.md `
  --document-type 通知 `
  --output 临时文件\公文格式检查_dry_run.md `
  --dry-run
```

正式调用 DeepSeek 时去掉 `--dry-run`；也可用 `--provider dashscope --model qwen-plus` 调用 Qwen。

## API

```powershell
uvicorn src.agents.official_document_review.api:app --reload --port 8010
```

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/review `
  -ContentType "application/json" `
  -Body '{"document_path":"src/agents/official_document_review/examples/示例通知.md","document_type":"通知","dry_run":true}'
```

## MCP

stdio:

```powershell
python -m src.agents.official_document_review.mcp_server
```

HTTP:

```powershell
python -m src.agents.official_document_review.mcp_server --transport http --host 127.0.0.1 --port 8010 --path /mcp
```

Tool 名称为 `review_official_document`，接收 `document_base64`、`document_filename`、`document_type` 和 `dry_run`。

## OpenAI-compatible LLM

```powershell
uvicorn src.agents.official_document_review.openai_compatible_api:app --host 0.0.0.0 --port 8013
```

模型 ID 为 `official-document-review-agent`。提示词仍推荐使用 `公文文件：` 区块；也兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。

```text
公文类型：通知

附件：
- 通知.docx: http://minio.example/notice.docx?X-Amz-Signature=...

输出要求：请输出公文格式检查报告。
```

URL 必须能被智能体服务所在环境访问；若使用 MinIO 预签名 URL，不要使用服务进程无法访问的 `localhost`。

## 环境变量

- `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`
- 可选 `OFFICIAL_DOCUMENT_REVIEW_MODEL`
- 可选 `OFFICIAL_DOCUMENT_REVIEW_BASE_URL`

## 边界

第一版不接入 FastGPT 原工作流中的内网检测服务，不处理扫描 PDF OCR，也不生成带批注的 Word 修订稿。本报告为格式辅助检查，不替代单位公文审核流程。
