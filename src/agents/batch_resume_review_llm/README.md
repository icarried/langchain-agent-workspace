# Batch Resume Review LLM Agent

`batch-resume-review-llm` 是从 `batch-resume-review` 隔离复制出来的 OpenAI-compatible 流式适配版。原智能体保持不变；本智能体面向 Dify、FastGPT 等平台的自定义 LLM 节点，让平台按模型调用方式接入批量简历审查并流式显示进度和最终报告。

## 能力

- 保留原批量简历审查能力：PDF、DOC、DOCX、MD、TXT 解析，提示词注入筛除，硬条件判断，候选人评分排序，待复核标记和百炼 OCR。
- 保留同步 REST：`GET /health`、`POST /review`。
- 保留 MCP：stdio 和 HTTP MCP，默认 HTTP 端口仍为 `8005`。
- 新增 OpenAI-compatible Chat Completions：`GET /v1/models`、`POST /v1/chat/completions`。
- 模型 ID：`batch-resume-review-agent`。

## 启动 OpenAI-compatible 服务

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

端口沿用原 `batch-resume-review` API 的 `8006`。不要同时启动原智能体和本智能体。

## Dify / FastGPT 配置

把本服务配置为 OpenAI-compatible 自定义模型：

- Base URL: `http://<服务地址>:8006/v1`
- Model: `batch-resume-review-agent`
- API Key: 可填写平台要求的任意占位值；当前服务不读取真实平台密钥。
- Stream: 开启。

推荐在 LLM 节点提示词中传入：

```text
岗位要求：要求本科及以上学历，熟悉 Python，有工业 AI 项目经验。

简历文件：
http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...

输出要求：请输出批量简历审查与排序报告。
```

`简历文件：` 后可以放服务端本地路径或 HTTP(S) 预签名 URL。FastGPT/MinIO 的端口映射兼容环境变量与原智能体一致。

## Chat Completions

非流式请求：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8006/v1/chat/completions `
  -ContentType "application/json" `
  -Body '{
    "model": "batch-resume-review-agent",
    "stream": false,
    "dry_run": true,
    "messages": [
      {
        "role": "user",
        "content": "岗位要求：要求本科。\n简历文件：\nsrc\\agents\\batch_resume_review_llm\\examples\\候选人A_工业AI.md"
      }
    ]
  }'
```

流式请求返回 `text/event-stream`，事件格式兼容 OpenAI `chat.completion.chunk`，最后返回 `data: [DONE]`。内部仍调用原两阶段审查流程，不降低审查质量。

## 同步 REST 和 MCP

同步 REST 仍可启动：

```powershell
uvicorn src.agents.batch_resume_review_llm.api:app --host 0.0.0.0 --port 8006
```

MCP 仍可启动：

```powershell
python -m src.agents.batch_resume_review_llm.mcp_server
python -m src.agents.batch_resume_review_llm.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp
```

## 验证

```powershell
python -m pytest tests\agents\test_batch_resume_review_llm.py -q
ruff check src\agents\batch_resume_review_llm tests\agents\test_batch_resume_review_llm.py
```
