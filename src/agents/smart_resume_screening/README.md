# smart-resume-screening

## 统一平台入口

生产环境和 Dify/FastGPT 使用统一网关，而非独立 OpenAI 端口：

```text
Base URL: http://<可达网关地址>:8008/v1
Model: smart-resume-screening-agent
Stream: 开启
```

生产启用鉴权时发送 `Authorization: Bearer <AGENT_GATEWAY_API_KEY>`。若调用平台在 Docker 容器内，`127.0.0.1` 是平台容器自身；应从调用容器验证网关地址。当前 `ai-app-platform` backend 应使用 `http://172.27.0.1:8008/v1`，长期推荐共享网络 DNS `http://gateway:8008/v1`。详见 `docs/development/AGENT_GATEWAY.md`。

`smart-resume-screening` 是根据 FastGPT 导出工作流“智能简历筛选”的有效经验转化而来的轻量智能体。它保留岗位参数、硬性条件、优先条件、淘汰条件、量化评分和排行榜输出，但不复制原工作流的一整段大提示词。

## 能力范围

- 支持多份本地 DOCX、文本型 PDF、TXT、MD 简历。
- 支持岗位 JD 或命令行参数配置硬性、加分和淘汰条件。
- 输出候选人状态、分数、优势、风险和推荐意见。
- 支持 CLI、REST API 和 MCP；支持 `--dry-run`，不调用模型。

## CLI

```powershell
python -m src.agents.smart_resume_screening screen `
  src\agents\smart_resume_screening\examples\候选人A_匹配.md `
  src\agents\smart_resume_screening\examples\候选人B_缺硬性.md `
  --job-description src\agents\smart_resume_screening\examples\人工智能岗位要求.md `
  --output 临时文件\智能简历筛选_dry_run.md `
  --dry-run
```

正式调用 DeepSeek 时去掉 `--dry-run`。

## API

```powershell
uvicorn src.agents.smart_resume_screening.api:app --reload --port 8011
```

主接口为 `POST /screen`。

## MCP

```powershell
python -m src.agents.smart_resume_screening.mcp_server
python -m src.agents.smart_resume_screening.mcp_server --transport http --host 127.0.0.1 --port 8011 --path /mcp
```

Tool 名称为 `screen_resumes`。

## OpenAI-compatible LLM

以下命令只用于本地单 worker 调试：

```powershell
uvicorn src.agents.smart_resume_screening.openai_compatible_api:app --host 0.0.0.0 --port 8012
```

模型 ID 为 `smart-resume-screening-agent`。提示词仍推荐使用 `岗位要求：` 和 `简历文件：` 区块；同时兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。

```text
岗位要求：
职位名称：AI 应用开发工程师
硬性条件：本科，计算机，Python

附件：
- 候选人A.pdf: http://minio.example/candidate-a.pdf?X-Amz-Signature=...
- 候选人B.docx: http://minio.example/candidate-b.docx?X-Amz-Signature=...

输出要求：请输出智能简历筛选排行榜。
```

URL 必须能被智能体服务所在环境访问；若使用 MinIO 预签名 URL，不要使用服务进程无法访问的 `localhost`。生产环境通过 `AGENT_REMOTE_ALLOWED_HOSTS`、`AGENT_REMOTE_MAX_BYTES`、`AGENT_REMOTE_TIMEOUT_SECONDS` 控制远程附件；仅在签名 Host 与传输地址不同时使用 `AGENT_REMOTE_TRANSPORT_OVERRIDES`，不要修改签名 URL。

推荐显式写 `岗位要求：`，但平台只把用户正文原样放在 `附件：` 前面时也可以工作：只要已识别到简历文件，且没有显式 `岗位要求：` / `JD：` 区块，服务会把 `附件：`、`简历文件：` 或 `输出要求：` 之前的正文当作岗位要求。

## 环境变量

- `DEEPSEEK_API_KEY`
- 可选 `SMART_RESUME_SCREENING_MODEL`
- 可选 `SMART_RESUME_SCREENING_BASE_URL`

## 与现有批量简历智能体的区别

`batch-resume-review-llm` 更适合完整招聘流程、OCR、远程 URL、学历高校参照和复杂报告；本智能体更像 FastGPT 中的结构化初筛配置器，适合快速验证岗位条件、候选人排名和筛选口径。
