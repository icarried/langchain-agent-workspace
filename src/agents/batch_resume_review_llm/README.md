# Batch Resume Review LLM Agent

`batch-resume-review-llm` 是批量简历审查的唯一业务实现，并提供 OpenAI-compatible 流式适配。本智能体面向 Dify、FastGPT 等平台的自定义 LLM 节点；旧 `batch-resume-review` 包已移除。

## 能力

- 保留原批量简历审查能力：PDF、DOC、DOCX、MD、TXT 解析，提示词注入筛除，硬条件判断，候选人评分排序和待复核标记。正式审查报告和 MCP 返回均包含六维评分卡：分项得分/上限、简历证据、得分说明及扣分或待核验项；六项合计等于总分。文本型 PDF 直接解析；扫描页和图片型 DOCX 复用工作区 GPU Stack `paddleocr-vl-1.6` OCR。
- 保留同步 REST：`GET /health`、`POST /review`。
- 生产 MCP 统一通过 `http://<host>:8008/mcp`，聚合 tool 名称为 `batch_resume_review`；stdio 和独立 HTTP `8005` 仅用于单智能体调试或独立交付。
- 新增 OpenAI-compatible Chat Completions：`GET /v1/models`、`POST /v1/chat/completions`。
- 模型 ID：`batch-resume-review-agent`。

## 统一入口

生产环境运行根目录 Compose，或本机运行 `python -m src.agent_gateway dev --port 8008`。平台统一配置：

- Base URL: `http://<服务地址>:8008/v1`
- Model: `batch-resume-review-agent`
- API Key: `AGENT_GATEWAY_API_KEY`；未启用鉴权时可填占位值。
- Stream: 开启。

若平台调用方在 Docker 容器内，`127.0.0.1` 指向调用方容器而不是网关。当前 `ai-app-platform` backend 应使用 `http://172.27.0.1:8008/v1`；网络重建后需要重新验证，长期推荐共享网络 DNS `http://gateway:8008/v1`。完整部署、健康检查和故障隔离说明见 `docs/development/AGENT_GATEWAY.md`。

以下命令只用于单 worker 调试：

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

独立 `8006` 不进入生产 Compose，也不作为平台推荐入口。

## Dify / FastGPT 提示词

推荐在 LLM 节点提示词中传入：

```text
岗位要求：要求本科及以上学历，熟悉 Python，有工业 AI 项目经验。

简历文件：
http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...

输出要求：请输出批量简历审查与排序报告。
```

`简历文件：` 后可以放服务端本地路径或 HTTP(S) 预签名 URL。生产环境使用 `AGENT_REMOTE_ALLOWED_HOSTS`、`AGENT_REMOTE_MAX_BYTES`、`AGENT_REMOTE_TIMEOUT_SECONDS` 限制远程附件；仅在签名 Host 与传输地址不同时配置 `AGENT_REMOTE_TRANSPORT_OVERRIDES`，原 URL 查询签名和 Host 不会被改写。

平台如果在模型对话上传文件后自动生成 `附件：` 列表，也可以直接传入：

```text
岗位要求：要求本科及以上学历，熟悉 Python。

附件：
- 候选人A.pdf: http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
- 候选人B.docx: http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...

输出要求：请输出批量简历审查与排序报告。
```

OpenAI content parts 中的 `file_url.url` 和 `image_url.url` 也会被识别为简历文件输入。URL 必须能被智能体服务所在环境访问；如果是 MinIO 预签名 URL，不要使用该服务进程、容器或 WSL 命名空间无法访问的 `localhost`。

PDF按页处理：可提取到有效文字的页面不会产生 OCR调用；无有效文字的页面使用 PyMuPDF
渲染为 PNG 后调用共享 `src/document_ocr/` provider。默认复用 `GPU_STACK_API_KEY`、
`GPU_STACK_BASE_URL` 和模型 `paddleocr-vl-1.6`；可用
`BATCH_RESUME_REVIEW_OCR_MODEL`、`BATCH_RESUME_REVIEW_OCR_BASE_URL`、
`BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MAX_PAGES` 覆盖。
`dry_run` 只跳过招聘审查模型，扫描文件所需 OCR仍会执行。

推荐显式写 `岗位要求：`，但平台只把用户正文原样放在 `附件：` 前面时也可以工作：只要已识别到简历文件，且没有显式 `岗位要求：` / `JD：` 区块，服务会把 `附件：`、`简历文件：` 或 `输出要求：` 之前的正文当作岗位要求。Markdown 标题和列表会原样保留。

## Chat Completions

非流式请求：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8008/v1/chat/completions `
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

默认 `thinking=true`：解析进度、文件接收和“仍在审查”等非最终输出会写入 `delta.reasoning_content`，最终报告写入 `delta.content`。如果平台不显示 think/reasoning 内容，可在请求中传 `"thinking": false`，让进度也走普通 `content`。

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

统一 MCP客户端只需配置 `http://<host>:8008/mcp` 和具有
`batch-resume-review:review` 权限的 Bearer token；无需再配置 `8005`。

正式调用的每个 `ranking`、`pending` 和 `excluded` 条目都带有 `score_breakdown`。六个
固定维度依次为学历/专业基础（20）、相关工作或实习（25）、项目与成果（25）、技能与工具（15）、
证据可信度（10）和沟通协作/文档（5）。筛除者的各项均为 `null`，不计入排名；这属于可供招聘人员
复核的事实与规则说明，不包含模型隐藏思维链。

MCP 同时返回 `report_html`，可直接嵌入支持安全 HTML 的预览界面。它由本次已经产生的候选人
决策渲染，不会重新下载、读取或嵌入每份简历的原始内容；报告只保留评分、证据摘要、风险和面试追问。

## 验证

```powershell
python -m pytest tests\agents\test_batch_resume_review_llm.py -q
ruff check src\agents\batch_resume_review_llm tests\agents\test_batch_resume_review_llm.py
```
