# Batch Resume Review Agent

`batch-resume-review` 一次审查多份简历，按同一岗位要求执行硬条件筛选、候选人评分和稳定排序。提示词注入或明确不满足硬条件者进入筛除名单且不参与排名；证据不足或存在冲突者保留分数和排名，并附加“需人工复核”标记。

## 工作流

```text
load_inputs
  -> split_resumes
  -> review_candidate_chunks
  -> decide_candidates
  -> filter_and_rank
  -> aggregate_report
```

- 简历片段可跨候选人并行审查，证据保留候选人编号、文件名、片段和元素编号。
- 候选人姓名从简历原文确定性提取，报告同时显示姓名和原始文件名，不信任模型自行改写的姓名。
- 每个候选人的片段结果独立汇总，单份解析或模型失败不会终止整个批次。
- `review_guide/批量简历审查与排序规则.md` 是唯一规则文件，集中定义筛除门槛、100 分量表、防注入和公平用工约束。
- 正式审查默认加载包内 `references/universities/`，使用教育部 985/211、带年份双一流名单和动态排名查询规则。
- 985/211、双一流和特殊科研院校作为有限加分优势；学历仅在 JD 明确最低要求时硬筛；技能熟练度只影响评分。
- 本地路径、HTTP(S) URL 和 MCP 上传统一支持 PDF、DOC、DOCX、MD、TXT；扫描 PDF 和图片型 Word 文件在本地文本不足时自动使用百炼 OCR。

## 文件解析与 OCR

- `.md`、`.txt` 直接按 UTF-8 文本读取；`.docx` 优先提取段落和表格；`.pdf` 按页优先提取文本。
- PDF 的无文本页面及图片型 DOCX 会调用百炼 `qwen3.5-ocr`，使用 `DASHSCOPE_API_KEY`。文本充分的文件不会产生 OCR 调用。
- 旧 `.doc` 先转换为 DOCX：Windows 可使用 Microsoft Word + pywin32，其他环境可安装 LibreOffice。转换时禁用 Word 自动化宏。
- `--dry-run` 只跳过筛选/评分大模型；若文件本身需要 OCR，解析阶段仍会调用百炼并产生对应费用。
- OCR 页面图像会发送给阿里云百炼。默认最多 50 个页面/内嵌图片，可用环境变量调整。
## CLI

```powershell
python -m src.agents.batch_resume_review review `
  path\to\candidate-a.pdf path\to\candidate-b.docx path\to\candidate-c.txt `
  --job-description path\to\jd.txt `
  --output 临时文件\批量简历审查报告.md `
  --dry-run
```

使用内置测试夹具：

```powershell
python -m src.agents.batch_resume_review review `
  src\agents\batch_resume_review\examples\候选示例1.md `
  src\agents\batch_resume_review\examples\候选示例2.md `
  src\agents\batch_resume_review\examples\候选示例3.md `
  src\agents\batch_resume_review\examples\候选示例4.md `
  --job-description src\agents\batch_resume_review\examples\人工智能开发工程师岗位要求.md `
  --output 临时文件\批量简历审查.md `
  --dry-run
```

## API

在工作空间根目录启动 REST API：

```powershell
conda activate langchain
uvicorn src.agents.batch_resume_review.api:app --reload --host 0.0.0.0 --port 8006
```

服务启动后可访问：

- 健康检查：`GET http://127.0.0.1:8006/health`
- 交互式接口文档：`http://127.0.0.1:8006/docs`
- 批量审查：`POST http://127.0.0.1:8006/review`

先使用内置测试夹具执行 dry-run。本地路径由 API 服务进程读取；`resume_paths` 也可直接传入 FastGPT/MinIO 生成的 HTTP(S) 预签名 URL：

```powershell
$body = @{
  resume_paths = @(
    ".\src\agents\batch_resume_review\examples\候选示例1.md"
    ".\src\agents\batch_resume_review\examples\候选示例2.md"
    ".\src\agents\batch_resume_review\examples\候选示例3.md"
    ".\src\agents\batch_resume_review\examples\候选示例4.md"
  )
  job_description_path = ".\src\agents\batch_resume_review\examples\人工智能开发工程师岗位要求.md"
  output_path = ".\临时文件\批量简历审查_API_dry_run.md"
  dry_run = $true
} | ConvertTo-Json -Depth 4

$result = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8006/review" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

$result | Select-Object `
  candidate_count, qualified_count, excluded_count, pending_count, chunk_count
$result.report
```

正式审查时将 `dry_run` 改为 `false`，并确保服务端已经配置对应 provider 的 API key。也可以直接传入岗位文本，并覆盖模型：

```json
{
  "resume_paths": [
    "D:\\resumes\\candidate-a.pdf",
    "D:\\resumes\\candidate-b.docx"
  ],
  "job_description_text": "要求本科及以上学历，具备 Python 和 AI 项目经验。",
  "provider": "deepseek",
  "model": "deepseek-chat",
  "dry_run": false
}
```

MinIO 预签名 URL 示例（签名值仅为占位符）：

```json
{
  "resume_paths": [
    "http://10.71.2.94:9000/fastgpt-private/chat/.../%E5%80%99%E9%80%89%E7%A4%BA%E4%BE%8B1.md?X-Amz-Signature=<presigned>"
  ],
  "job_description_text": "人工智能开发工程师岗位要求正文",
  "dry_run": false
}
```

`job_description_text` 必须是岗位要求正文，不是文件路径；若岗位要求保存在 API 服务端文件中，应改用 `job_description_path`。预签名 URL 应在过期前提交，API 会在进入模型工作流前读取内容。响应中的 `resume_paths`、报告和错误信息不会回显 URL 查询签名。

若 MinIO 由本机 WSL/Docker 暴露，Windows 可能只能通过 `127.0.0.1:9000` 访问，而预签名 URL 使用本机 WLAN 地址。loader 在确认 URL 主机确属本机地址、首次 HTTP 连接失败时，会自动改走相同端口的 localhost 连接，同时保留原始 `Host` 请求头，避免破坏 AWS V4 签名。非本机 URL、HTTPS URL和正常可达的 URL 不使用此回退。

若 Docker 发布端口与签名 URL 端口不同，例如 FastGPT URL 为 `10.71.2.94:9000`、实际 FastGPT MinIO 为 `127.0.0.1:9002`，可设置 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002`。该配置只改变 TCP 传输目标，签名 URL 和 `Host` 仍保持原值。

### FastGPT/MinIO 部署兼容层（维护必读）

当前本机部署同时存在两套 MinIO：宿主机 9000 是另一套实例；FastGPT MinIO 的 Docker 映射为 `宿主机 9002 -> 容器 9000`。FastGPT 仍生成以 `10.71.2.94:9000` 为 Host 的 AWS V4 预签名 URL，因此直接访问会落到错误实例并返回 `NoSuchKey`。

当前兼容链路为：

```text
签名 URL / Host: 10.71.2.94:9000
        ↓ 首次连接失败后，仅改 TCP 传输地址
实际连接: 127.0.0.1:9002
        ↓ Docker 发布端口
fastgpt-minio:9000
```

代码位置：`resume_loader.py::_localhost_fallback_request` 和 `_local_minio_transport_netloc`。配置位置：`.env.local` 的 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT`。不得直接把 URL 中的 `:9000` 字符串替换为 `:9002`，因为 `host` 在 `X-Amz-SignedHeaders` 中，会导致 `SignatureDoesNotMatch`。

更好的长期方案是修改 FastGPT 的 MinIO 外部访问/签名地址，使新预签名 URL 直接使用实际可达的 `10.71.2.94:9002`（或统一反向代理域名）。完成后应删除 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT`，让 loader 使用同端口 localhost 回退；若该地址从 Windows 可直接访问，则连回退也可删除。修改 FastGPT 配置前必须以实际部署版本的 compose/config 为准，不要猜环境变量名。

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `resume_paths` | 是 | 1 至 100 个服务端简历路径或 HTTP(S) URL；支持 PDF、DOC、DOCX、MD、TXT；扫描件会自动 OCR。输入不可重复。 |
| `job_description_path` | 二选一 | 服务端岗位要求文本文件路径。 |
| `job_description_text` | 二选一 | 直接传入岗位要求文本；与 `job_description_path` 至少提供一个。 |
| `review_guide_path` | 否 | 自定义统一审查规则 Markdown 路径；默认使用智能体内置规则。 |
| `output_path` | 否 | 服务端 Markdown 报告写入路径；不提供时仅在响应的 `report` 中返回报告。 |
| `provider` | 否 | 模型提供方，默认 `deepseek`，也支持 `dashscope`。 |
| `model` | 否 | 覆盖 provider 的默认模型名。 |
| `dry_run` | 否 | 默认 `false`；设为 `true` 时只验证文件解析和工作流，不调用模型、不产生真实排名。 |

主要响应字段包括完整 Markdown `report`，输入统计 `candidate_count`、`chunk_count`，结果统计 `qualified_count`、`excluded_count`、`pending_count`，以及明细列表 `ranking`、`excluded`、`pending`、`candidates`。有有效分数的待复核候选人会同时出现在 `ranking` 和 `pending` 中；`excluded` 与 `ranking` 互斥。

本地文件不存在时返回 `404`，参数或运行配置错误返回 `400`，请求结构校验失败返回 `422`。单份远程文件下载、格式或解析失败不会中断整批，而会作为该候选人的人工复核风险返回。API 应仅部署在受控内网；若设置 `BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS`，则只允许下载逗号分隔的主机名。

## MCP

```powershell
python -m src.agents.batch_resume_review.mcp_server
```

tool 名称为 `review_resumes`：

```json
{
  "resumes": [
    {"filename": "candidate-a.pdf", "content_base64": "<base64>"},
    {"filename": "candidate-b.docx", "content_base64": "<base64>"}
  ],
  "job_description_text": "岗位要求文本",
  "dry_run": false
}
```

MCP 接受 PDF、DOC、DOCX、MD、TXT；模型和密钥由服务端统一配置。

响应中的 `pending_count`、`pending` 表示需要附加复核的候选人；其中有有效分数者也会同时出现在 `ranking` 中。`excluded` 与 `ranking` 互斥。

支持 stdio 和 Streamable HTTP 两种调用方式：

```powershell
# stdio（默认，适合 MCP 客户端直接拉起）
python -m src.agents.batch_resume_review.mcp_server

# HTTP（适合独立服务部署）
python -m src.agents.batch_resume_review.mcp_server `
  --transport streamable-http --host 127.0.0.1 --port 8005 --path /mcp

# 内网可访问
python -m src.agents.batch_resume_review.mcp_server `
  --transport streamable-http --host 0.0.0.0 --port 8005 --path /mcp
```

单批支持 1 至 100 份简历，每份最大 10 MiB；PDF、DOC、DOCX、MD、TXT 均可上传，扫描件按需调用百炼 OCR。调用方应当只传递可信文件名和 base64 文件内容，不要传服务端路径。

完整的客户端配置、Python 调用示例、返回字段和错误处理见 `standalone/README.md` 与 `standalone/mcp_client_example.py`。

## 独立打包

```powershell
python scripts\package_agent_standalone.py `
  --agent batch_resume_review `
  --output-dir dist
```

生成的 `dist\batch-resume-review-agent-0.4.0.zip` 内含源码、审查规则、高校参考资料、安装元数据、MCP 配置和调用示例，不依赖本工作区的 `src.agents` 或 `src.reference_data`。解压后的安装与运行说明见压缩包根目录 `README.md`。

## 环境变量

- `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`
- 可选：`BATCH_RESUME_REVIEW_MODEL`
- 可选：`BATCH_RESUME_REVIEW_BASE_URL`
- 可选：`BATCH_RESUME_REVIEW_OCR_MODEL`，默认 `qwen3.5-ocr`
- 可选：`BATCH_RESUME_REVIEW_OCR_BASE_URL`，默认百炼北京地域兼容接口
- 可选：`BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS`，默认 `120`
- 可选：`BATCH_RESUME_REVIEW_OCR_MAX_PAGES`，默认 `50`
- 可选：`BATCH_RESUME_REVIEW_MIN_TEXT_CHARS`，低于该有效字符数时触发 OCR，默认 `12`
- 可选：`BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS`，逗号分隔的远程文件主机白名单，例如 `10.71.2.94,minio`
- 可选：`BATCH_RESUME_REVIEW_MAX_REMOTE_FILE_BYTES`，远程单文件上限，默认 `10485760`（10 MiB）
- 可选：`BATCH_RESUME_REVIEW_REMOTE_TIMEOUT_SECONDS`，远程读取超时，默认 `30`
- 可选：`BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT`，本机 MinIO 实际发布地址，例如 `http://127.0.0.1:9002`
