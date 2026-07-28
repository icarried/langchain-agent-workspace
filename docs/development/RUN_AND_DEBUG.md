# Run And Debug

## 推荐统一入口

OpenAI-compatible 智能体统一通过 `8008` 网关部署和接入，不再公开各智能体原有的 8006–8014 等端口：

```powershell
python -m src.agent_gateway dev --port 8008
```

FastGPT/Dify 使用 `http://<host>:8008/v1`，通过模型 ID 选择智能体。Docker Compose、模型列表、鉴权、远程附件、故障隔离和新知识库管理详见 [AGENT_GATEWAY.md](./AGENT_GATEWAY.md)。后文中的独立 API/MCP 命令仅用于单智能体调试，不是生产部署入口。

## 激活环境

```powershell
conda activate langchain
```

当前 `langchain` conda 环境已由用户创建完成。

## 加载环境变量

推荐在 Python 入口中使用：

```python
from dotenv import load_dotenv

load_dotenv(".env.local")
```

PowerShell 临时加载方式：

```powershell
Get-Content .env.local | ForEach-Object {
  if ($_ -and -not $_.StartsWith("#")) {
    $name, $value = $_.Split("=", 2)
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
  }
}
```

## 推荐开发命令

```powershell
python -m pytest
ruff check .
ruff format .
```

如果通过 `conda run` 执行并遇到 Windows GBK 输出编码问题，可临时设置：

```powershell
$env:PYTHONIOENCODING='utf-8'
conda run -n langchain python -m pytest
```

## LangChain / LangGraph 调试建议

- 将模型、工具、prompt 和图结构分开放置，方便单独测试。
- 给每个工具写最小单元测试，避免 Agent 执行时才发现参数错误。
- 对 LangGraph 节点记录输入、输出和状态变化。
- 开启 LangSmith tracing 时设置：

```text
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your-langsmith-key>
LANGCHAIN_PROJECT=agent-workspace-dev
```

## 建议入口文件

后续可以添加：

```text
src/agents/main.py       # 命令行运行 Agent
src/agents/graph.py      # LangGraph 图定义
src/config/settings.py   # 环境变量和模型配置
```

## 知识库智能体（新架构）

`langchain_knowledge_base` worker 复用工作区级 `src/knowledge_base/` 核心。旧 `kb_api`、Langflow、primary/secondary 配置和旧 Chroma 数据已删除且不迁移。

关键变量包括 `KB_DATA_ROOT`、`KB_NAMESPACE`、`KB_DEFAULT_NAME`、`KB_CHAT_MODEL`、`KB_EMBEDDING_MODEL`、对应 API key/base URL、`KB_TOP_K` 和 `KB_MIN_RELEVANCE_SCORE`。知识库默认写入 `data/knowledge_bases/<namespace>/<name>/`。

本地管理：

```powershell
python -m src.knowledge_base documents-dir default
python -m src.knowledge_base ingest default
python -m src.knowledge_base retrieve default "检索问题"
python -m src.knowledge_base list
```

单独启动 worker 仅用于调试：

```powershell
uvicorn src.agents.langchain_knowledge_base.openai_compatible_api:app --host 127.0.0.1 --port 18008
```

worker 内部管理接口为 `GET /v1/knowledge-bases`、`POST /v1/knowledge-bases/{name}/ingest` 和 `POST /v1/knowledge-bases/{name}/retrieval`。这些接口不由网关公开；平台问答统一使用 `http://<host>:8008/v1` 和模型 `langchain-knowledge-base-agent`。详见 [AGENT_GATEWAY.md](./AGENT_GATEWAY.md)。

## 八部门隔离知识库智能体

本地只启动该 worker：

```powershell
python -m src.agent_gateway dev --port 8008 --models department-knowledge-base-agent
```

该方式适合 readiness、问答和 `dry_run`。真实保存使用根 Compose，因为专属 MinIO
只通过 Compose DNS提供服务且不发布宿主机端口。

同一个模型通过顶层扩展字段切换部门：

```json
{
  "model": "department-knowledge-base-agent",
  "knowledge_id": "marketing",
  "messages": [{"role": "user", "content": "当前市场活动审批流程是什么？"}],
  "stream": true,
  "thinking": true
}
```

保存文件时在消息中明确说明“保存/入库/归档”，并通过 `files` 或 content parts传入
平台 MinIO预签名 URL。有附件但没有保存意图不会写入。`dry_run=true` 不调用模型、
不下载附件且不写入，可用于平台配置验证。

生产 Compose启用项目专属 `department-kb-minio`，只在内部监听
`department-kb-minio:9000`，不占用宿主机 9000/9002。启动前必须在 `.env.local`
配置 `DEPARTMENT_KB_MINIO_ACCESS_KEY` 和 `DEPARTMENT_KB_MINIO_SECRET_KEY`。
完整部门 ID、对象键、OCR和备份说明见
`src/agents/department_knowledge_base/README.md`。

## 招标文件格式审查智能体

先执行 dry-run，确认 docx 可解析且分块合理：

```powershell
conda activate langchain
python -m src.agents.tender_format_review review `
  path\to\招标文件.docx `
  --review-guide C:\Users\Lenovo\Desktop\招标文件审查事项.md `
  --catalog 临时文件\招标文件参考目录.txt `
  --output 临时文件\招标文件格式审查报告.md `
  --dry-run
```

调用 DeepSeek：

```powershell
python -m src.agents.tender_format_review review `
  path\to\招标文件.docx `
  --review-guide C:\Users\Lenovo\Desktop\招标文件审查事项.md `
  --catalog 临时文件\招标文件参考目录.txt `
  --output 临时文件\招标文件格式审查报告.md `
  --provider deepseek
```

调用 DashScope/Qwen：

```powershell
python -m src.agents.tender_format_review review `
  path\to\招标文件.docx `
  --review-guide C:\Users\Lenovo\Desktop\招标文件审查事项.md `
  --catalog 临时文件\招标文件参考目录.txt `
  --output 临时文件\招标文件格式审查报告.md `
  --provider dashscope --model qwen-plus
```

启动 API 服务：

```powershell
conda activate langchain
uvicorn src.agents.tender_format_review.api:app --reload --port 8001
```

用最小 docx 样例测试 API dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8001/review `
  -ContentType "application/json" `
  -Body '{"docx_path":"./临时文件/仅包含一行文字的文件.docx","dry_run":true}'
```

更多智能体 API 封装经验见 `docs/development/AGENT_API_WRAPPING_GUIDE.md`。

### OpenAI-compatible LLM 入口

用于 Dify/FastGPT 自定义模型节点流式调用，不替代原 `/review` API：

```powershell
uvicorn src.agents.tender_format_review.openai_compatible_api:app --host 0.0.0.0 --port 8007
```

模型配置：

- Base URL: `http://<服务地址>:8008/v1`（生产统一网关）
- Model: `tender-format-review-agent`
- Stream: 开启
- API Key: 当前服务不校验，可填平台要求的占位值

默认 `thinking=true`：流式进度和心跳会放在 `delta.reasoning_content`，最终报告放在 `delta.content`。如果平台不展示 think/reasoning 内容，可在请求中传 `"thinking": false`，让进度也走普通 `content`。

LLM 节点提示词推荐格式：

```text
招标文件：
http://minio.example/bucket/待审招标文件.docx?X-Amz-Signature=...

输出要求：请输出招标文件格式审查报告。
```

`招标文件` 也可以是服务端本地 `.docx` 路径。FastGPT 文件变量渲染为 JSON 数组时，服务会读取数组中的第一个文件链接；平台自动生成的 `附件：` 列表和 OpenAI content parts 中的 `file_url.url` / `image_url.url` 也会被识别。远程 `.docx` 会临时下载后交给原 `review_tender_format` 服务层；可用 `TENDER_REVIEW_MAX_REMOTE_FILE_BYTES` 和 `TENDER_REVIEW_REMOTE_TIMEOUT_SECONDS` 调整大小上限和超时。URL 必须能被智能体服务所在环境访问，MinIO 预签名 URL 不要使用该服务进程无法访问的 `localhost`。

特殊 MinIO 网络不再由招标智能体硬编码。需要签名 Host 与实际传输地址分离时配置共享的 `AGENT_REMOTE_TRANSPORT_OVERRIDES`；下载会保留原始 Host 和完整查询签名。修好 MinIO 外部签名地址后应删除该环境映射。

## 简历审查智能体

先执行 dry-run，确认简历可解析且分块合理：

```powershell
conda activate langchain
python -m src.agents.resume_review review `
  path\to\resume.pdf `
  --job-description path\to\jd.txt `
  --output 临时文件\简历审查报告.md `
  --dry-run
```

也可以直接使用内置“人工智能开发工程师”Markdown 测试夹具执行真实模型审查。Markdown 仅用于本地样例维护，不是 MCP 输入协议：

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m src.agents.resume_review review `
  src\agents\resume_review\examples\示例简历_人工智能开发工程师.md `
  --job-description src\agents\resume_review\examples\人工智能开发工程师岗位要求.md `
  --provider deepseek --model deepseek-v4-flash `
  --output 临时文件\简历审查_人工智能开发工程师_deepseek-v4-flash.md
```

如果暂时没有岗位 JD，也可以只审查简历质量和背调前置风险：

```powershell
python -m src.agents.resume_review review `
  path\to\resume.txt `
  --output 临时文件\简历审查报告.md `
  --dry-run
```

未提供 JD 时，报告会写明“未提供 JD，岗位匹配未评分”。正式模型审查会按三个维度并行检查：基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配。

调用 DeepSeek：

```powershell
python -m src.agents.resume_review review `
  path\to\resume.docx `
  --job-description path\to\jd.txt `
  --provider deepseek
```

调用 DashScope/Qwen：

```powershell
python -m src.agents.resume_review review `
  path\to\resume.txt `
  --job-description path\to\jd.txt `
  --provider dashscope --model qwen-plus
```

启动 API 服务：

```powershell
conda activate langchain
uvicorn src.agents.resume_review.api:app --reload --port 18004
```

用文本简历测试 API dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:18004/review `
  -ContentType "application/json" `
  -Body '{"resume_path":"./临时文件/sample_resume.txt","job_description_text":"招聘 Python 后端工程师","dry_run":true}'
```

启动 MCP server：

```powershell
conda activate langchain
python -m src.agents.resume_review.mcp_server
```

默认是 stdio MCP，MCP client 会按配置启动命令并通过标准输入/输出调用 tool。若需要跨进程或多个客户端共享，可启动 HTTP MCP：

```powershell
python -m src.agents.resume_review.mcp_server --transport http --host 127.0.0.1 --port 8003 --path /mcp
```

MCP tool 名称为 `review_resume`，接收 base64 文件上传：

```json
{
  "resume_base64": "<base64 encoded docx/pdf/txt>",
  "resume_filename": "candidate.pdf",
  "job_description_text": "岗位 JD 文本",
  "dry_run": true
}
```

MCP 中的岗位要求是 `job_description_text` 普通文本，简历是 DOCX、文本型 PDF 或 TXT 文件内容；不上传测试用 Markdown 文件。

启动 MCP server：

```powershell
conda activate langchain
python -m src.agents.tender_format_review.mcp_server
```

默认是 stdio MCP：通常不需要提前起常驻服务，MCP client 会根据配置按需启动这个命令，并通过标准输入/输出调用 tool。手工运行时终端会被占用。

如果需要跨进程或多个客户端共享，可启动 HTTP MCP：

```powershell
python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp
```

在 Codex 沙箱或后台常驻场景中，`conda run` 可能因为用户 Temp 目录或外部 conda 环境包读取权限失败。已验证的可行方式是直接调用 `langchain` 环境里的 Python 解释器，并把日志写到工作区：

```powershell
$out = "E:\My_sorcode\--创建智能体工作空间--\临时文件\tender_format_review_mcp.out.log"
$err = "E:\My_sorcode\--创建智能体工作空间--\临时文件\tender_format_review_mcp.err.log"
Start-Process -WindowStyle Hidden `
  -FilePath "C:\Users\Lenovo\.conda\envs\langchain\python.exe" `
  -ArgumentList @(
    "-m", "src.agents.tender_format_review.mcp_server",
    "--transport", "http",
    "--host", "127.0.0.1",
    "--port", "8002",
    "--path", "/mcp"
  ) `
  -WorkingDirectory "E:\My_sorcode\--创建智能体工作空间--" `
  -RedirectStandardOutput $out `
  -RedirectStandardError $err
```

HTTP MCP 连接地址为 `http://127.0.0.1:8002/mcp`。它不是普通 REST API，需要使用支持 MCP 的 client 或 SDK 调用。

MCP tool 名称为 `review_tender_format`。推荐先用以下参数做 dry-run：

```json
{
  "docx_path": "./临时文件/仅包含一行文字的文件.docx",
  "dry_run": true
}
```

stdio MCP client 配置示例：

```json
{
  "mcpServers": {
    "tender-format-review": {
      "command": "D:\\ProgramData\\miniforge3\\Library\\bin\\conda.bat",
      "args": [
        "run",
        "-n",
        "langchain",
        "python",
        "-m",
        "src.agents.tender_format_review.mcp_server"
      ],
      "cwd": "E:\\My_sorcode\\--创建智能体工作空间--"
    }
  }
}
```

也可以用仓库内脚本直接验证 stdio MCP 调用：

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts\call_tender_format_review_mcp.py --transport stdio
```

启动 HTTP MCP 后，可用同一个脚本验证 HTTP MCP 调用：

```powershell
$env:PYTHONIOENCODING='utf-8'
C:\Users\Lenovo\.conda\envs\langchain\python.exe scripts\call_tender_format_review_mcp.py --transport http --url http://127.0.0.1:8002/mcp
```

更多智能体 MCP 封装经验见 `docs/development/AGENT_MCP_WRAPPING_GUIDE.md`。

## 合同审查智能体

`contract-review` 来自 FastGPT 导出工作流“合同审查大师”的经验转化，重点保留表单上下文、六维审查、评分评级和整改建议。

先执行 dry-run，确认合同可解析且分块合理：

```powershell
conda activate langchain
python -m src.agents.contract_review review `
  src\agents\contract_review\examples\示例服务合同.md `
  --client-role 甲方 `
  --contract-type 技术服务合同 `
  --transaction-background "甲方采购设备运行数据分析平台开发服务" `
  --output 临时文件\合同审查_dry_run.md `
  --dry-run
```

正式调用 DeepSeek：

```powershell
python -m src.agents.contract_review review `
  path\to\contract.docx `
  --client-role 甲方 `
  --contract-type 采购合同 `
  --transaction-background "采购设备与配套服务" `
  --provider deepseek
```

启动 API 服务：

```powershell
uvicorn src.agents.contract_review.api:app --reload --port 8009
```

用内置样例测试 API dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8009/review `
  -ContentType "application/json" `
  -Body '{"contract_path":"src/agents/contract_review/examples/示例服务合同.md","client_role":"甲方","contract_type":"技术服务合同","transaction_background":"采购数据分析平台","dry_run":true}'
```

启动 MCP server：

```powershell
python -m src.agents.contract_review.mcp_server
python -m src.agents.contract_review.mcp_server --transport http --host 127.0.0.1 --port 8009 --path /mcp
```

MCP tool `review_contract` 接收 base64 文件上传：

```json
{
  "contract_base64": "<base64 encoded docx/pdf/txt>",
  "contract_filename": "contract.docx",
  "client_role": "甲方",
  "contract_type": "技术服务合同",
  "transaction_background": "交易背景文本",
  "dry_run": true
}
```

### OpenAI-compatible LLM 入口

用于 FastGPT/Dify 自定义模型节点流式调用，不替代原 `/review` API：

```powershell
uvicorn src.agents.contract_review.openai_compatible_api:app --host 0.0.0.0 --port 8014
```

模型配置：

- Base URL: `http://<服务地址>:8008/v1`（生产统一网关）
- Model: `contract-review-agent`
- Stream: 开启
- API Key: 当前服务不校验，可填平台要求的占位值

LLM 节点提示词推荐格式：

```text
委托方角色：甲方
合同类型：技术服务合同
交易背景：甲方采购设备运行数据分析平台开发服务

合同文件：
src/agents/contract_review/examples/示例服务合同.md

输出要求：请输出合同审查报告。
```

也兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。URL 必须能被智能体服务所在环境访问，MinIO 预签名 URL 不要使用该服务进程无法访问的 `localhost`。

## 公文格式检查智能体

`official-document-review` 来自 FastGPT 导出工作流“公文优化”的经验转化，重点保留“文件检测 -> 检测结果整理输出”的分层。第一版使用本地确定性检查，不依赖原工作流中的内网 HTTP 检测地址。

先执行 dry-run，确认公文可解析且检查结果正常：

```powershell
conda activate langchain
python -m src.agents.official_document_review review `
  src\agents\official_document_review\examples\示例通知.md `
  --document-type 通知 `
  --output 临时文件\公文格式检查_dry_run.md `
  --dry-run
```

正式调用 DeepSeek 美化报告：

```powershell
python -m src.agents.official_document_review review `
  path\to\official-document.docx `
  --document-type 通知 `
  --provider deepseek
```

启动 API 服务：

```powershell
uvicorn src.agents.official_document_review.api:app --reload --port 8010
```

用内置样例测试 API dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/review `
  -ContentType "application/json" `
  -Body '{"document_path":"src/agents/official_document_review/examples/示例通知.md","document_type":"通知","dry_run":true}'
```

启动 MCP server：

```powershell
python -m src.agents.official_document_review.mcp_server
python -m src.agents.official_document_review.mcp_server --transport http --host 127.0.0.1 --port 8010 --path /mcp
```

MCP tool `review_official_document` 接收 base64 文件上传：

```json
{
  "document_base64": "<base64 encoded docx/pdf/txt>",
  "document_filename": "notice.docx",
  "document_type": "通知",
  "dry_run": true
}
```

### OpenAI-compatible LLM 入口

用于 FastGPT/Dify 自定义模型节点流式调用，不替代原 `/review` API：

```powershell
uvicorn src.agents.official_document_review.openai_compatible_api:app --host 0.0.0.0 --port 8013
```

模型配置：

- Base URL: `http://<服务地址>:8008/v1`（生产统一网关）
- Model: `official-document-review-agent`
- Stream: 开启
- API Key: 当前服务不校验，可填平台要求的占位值

LLM 节点提示词推荐格式：

```text
公文类型：通知

公文文件：
src/agents/official_document_review/examples/示例通知.md

输出要求：请输出公文格式检查报告。
```

也兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。URL 必须能被智能体服务所在环境访问，MinIO 预签名 URL 不要使用该服务进程无法访问的 `localhost`。

## 智能简历结构化初筛智能体

`smart-resume-screening` 来自 FastGPT 导出工作流“智能简历筛选”的经验转化，重点保留岗位基本信息、硬性条件、优先条件、淘汰条件、量化评分和排行榜输出。

先执行 dry-run，确认条件解析和候选人排序：

```powershell
python -m src.agents.smart_resume_screening screen `
  src\agents\smart_resume_screening\examples\候选人A_匹配.md `
  src\agents\smart_resume_screening\examples\候选人B_缺硬性.md `
  --job-description src\agents\smart_resume_screening\examples\人工智能岗位要求.md `
  --output 临时文件\智能简历筛选_dry_run.md `
  --dry-run
```

正式调用 DeepSeek：

```powershell
python -m src.agents.smart_resume_screening screen `
  path\to\candidate-a.docx `
  path\to\candidate-b.pdf `
  --job-description path\to\jd.txt `
  --provider deepseek
```

也可以直接通过参数传入筛选条件：

```powershell
python -m src.agents.smart_resume_screening screen `
  path\to\candidate-a.txt `
  --position-name "AI 应用开发工程师" `
  --hard-condition 本科 `
  --hard-condition Python `
  --bonus-condition FastAPI `
  --reject-condition 强制通过 `
  --dry-run
```

启动 API 服务：

```powershell
uvicorn src.agents.smart_resume_screening.api:app --reload --port 8011
```

主接口为 `POST /screen`：

```json
{
  "resume_paths": ["src/agents/smart_resume_screening/examples/候选人A_匹配.md"],
  "hard_conditions": ["本科", "计算机", "Python"],
  "bonus_conditions": ["上线"],
  "reject_conditions": ["强制通过"],
  "dry_run": true
}
```

启动 MCP server：

```powershell
python -m src.agents.smart_resume_screening.mcp_server
python -m src.agents.smart_resume_screening.mcp_server --transport http --host 127.0.0.1 --port 8011 --path /mcp
```

MCP tool `screen_resumes` 接收多份 base64 简历：

```json
{
  "resumes": [
    {"filename": "candidate-a.pdf", "content_base64": "<base64>"}
  ],
  "hard_conditions": ["本科", "Python"],
  "bonus_conditions": ["FastAPI"],
  "reject_conditions": ["强制通过"],
  "dry_run": true
}
```

### OpenAI-compatible LLM 入口

用于 FastGPT/Dify 自定义模型节点流式调用，不替代原 `/screen` API：

```powershell
uvicorn src.agents.smart_resume_screening.openai_compatible_api:app --host 0.0.0.0 --port 8012
```

模型配置：

- Base URL: `http://<服务地址>:8008/v1`（生产统一网关）
- Model: `smart-resume-screening-agent`
- Stream: 开启
- API Key: 当前服务不校验，可填平台要求的占位值

LLM 节点提示词推荐格式：

```text
岗位要求：
职位名称：AI 应用开发工程师
硬性条件：本科，计算机，Python
优先条件：FastAPI，上线
淘汰条件：强制通过

简历文件：
src/agents/smart_resume_screening/examples/候选人A_匹配.md
src/agents/smart_resume_screening/examples/候选人B_缺硬性.md

输出要求：请输出智能简历筛选排行榜。
```

FastGPT 文件变量渲染为 JSON 数组时，服务会读取数组中的文件链接或服务端路径；平台自动生成的 `附件：` 列表和 OpenAI content parts 中的 `file_url.url` / `image_url.url` 也会被识别。URL 必须能被智能体服务所在环境访问，MinIO 预签名 URL 不要使用该服务进程无法访问的 `localhost`。当前轻量初筛入口复用 `screen_resumes`，适合服务端本地路径；需要远程 MinIO URL、OCR 或多格式复杂解析时优先使用 `batch-resume-review-llm`。

推荐显式写 `岗位要求：`。如果平台只把用户正文原样放在 `附件：` 前面，`smart-resume-screening` 会在已识别到简历文件且没有显式 `岗位要求：` / `JD：` 时，把 `附件：`、`简历文件：` 或 `输出要求：` 之前的正文作为岗位要求。

## 批量简历审查与排序智能体

使用多份本地测试夹具执行 dry-run：

```powershell
python -m src.agents.batch_resume_review_llm review `
  src\agents\batch_resume_review_llm\examples\候选人A_工业AI.md `
  src\agents\batch_resume_review_llm\examples\候选人B_条件不符.md `
  src\agents\batch_resume_review_llm\examples\候选人C_待确认.md `
  --job-description src\agents\batch_resume_review_llm\examples\人工智能开发工程师岗位要求.md `
  --output 临时文件\批量简历审查_dry_run.md `
  --dry-run
```

正式调用时去掉 `--dry-run`，可用 `--provider` 和 `--model` 覆盖服务端默认模型。提示词注入和明确不满足学历等硬条件者输出筛除理由且不参与排名；证据不足、学制或时间线待核验者仍参与 0-100 分排序，并在“附加复核项”中重复显示。技能熟练程度只影响分数，不作为硬筛。

启动 API：

```powershell
uvicorn src.agents.batch_resume_review_llm.api:app --reload --port 8006
```

API 的 `resume_paths` 可混合使用服务端本地路径与 FastGPT/MinIO HTTP(S) 预签名 URL。岗位要求正文传给 `job_description_text`；服务端岗位文件路径传给 `job_description_path`。生产内网建议设置 `BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS=10.71.2.94`，远程文件默认上限 10 MiB、超时 30 秒。

若 FastGPT 预签名 URL 使用 `10.71.2.94:9000`，但其 MinIO 实际发布为宿主机 `9002 -> 容器 9000`，设置 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002` 后重启 API。下载连接走 9002，签名 Host 仍保持 9000。

启动 stdio 或 HTTP MCP：

```powershell
python -m src.agents.batch_resume_review_llm.mcp_server
python -m src.agents.batch_resume_review_llm.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp
```

MCP tool `review_resumes` 接收多份实际简历和一份岗位要求文本：

```json
{
  "resumes": [
    {"filename": "candidate-a.pdf", "content_base64": "<base64>"},
    {"filename": "candidate-b.docx", "content_base64": "<base64>"}
  ],
  "job_description_text": "岗位要求文本",
  "dry_run": true
}
```

CLI、API 与 MCP 均接受 PDF、DOC、DOCX、MD、TXT。文本型文件优先本地解析；扫描 PDF 页面和图片型 Word 文件使用 `DASHSCOPE_API_KEY` 调用百炼 `qwen3.5-ocr`。旧 DOC 需要 Microsoft Word + pywin32（Windows）或 LibreOffice 转换。`--dry-run` 不调用筛选模型，但扫描件解析仍会调用 OCR。

独立打包并交付：

```powershell
python scripts\package_agent_standalone.py --agent batch_resume_review_llm --output-dir dist
```

ZIP 内的 `README.md` 包含独立安装、CLI、API、stdio/HTTP MCP 使用说明；`mcp-config.example.json` 和 `mcp_client_example.py` 可直接改路径后使用。通用封装约定见 `docs/development/AGENT_STANDALONE_PACKAGING_GUIDE.md`。

## 批量简历 OpenAI-compatible 流式适配智能体

`batch-resume-review-llm` 是批量简历唯一业务实现，供 Dify/FastGPT 自定义 OpenAI-compatible LLM 节点调用。旧 `batch-resume-review` 包已移除。

面向 FastGPT、Dify 等平台的人读版接入说明见 `docs/development/OPENAI_COMPATIBLE_LLM_PLATFORM_INTEGRATION.md`。

启动 OpenAI-compatible 服务：

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

模型配置：

- Base URL: `http://<服务地址>:8008/v1`（生产统一网关）
- Model: `batch-resume-review-agent`
- Stream: 开启
- API Key: 当前服务不校验，可填平台要求的占位值

LLM 节点提示词推荐格式：

```text
岗位要求：要求本科及以上学历，熟悉 Python。

简历文件：
http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...

输出要求：请输出批量简历审查与排序报告。
```

也兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。URL 必须能被智能体服务所在环境访问，MinIO 预签名 URL 不要使用该服务进程无法访问的 `localhost`。

推荐显式写 `岗位要求：`。如果平台只把用户正文原样放在 `附件：` 前面，`batch-resume-review-llm` 会在已识别到简历文件且没有显式 `岗位要求：` / `JD：` 时，把 `附件：`、`简历文件：` 或 `输出要求：` 之前的正文作为岗位要求。

本地 dry-run 验证：

```powershell
python -m pytest tests\agents\test_batch_resume_review_llm.py -q
```

## 高校参照数据维护

工作区共享资料位于 `src/reference_data/universities/`；可独立交付的批量智能体同时在自身 `references/universities/` 保存版本化副本：

- 985/211：教育部固定历史名单，只修正别名或录入错误。
- 双一流：文件名必须包含轮次和年份；教育部发布新一轮时新增文件，不覆盖旧版。
- 一本：按生源省份、招生年份、学校/校区和专业查询阳光高考及省级考试机构，不维护全国静态表。
- 世界排名：通过 QS、THE、ARWU、Leiden 官方动态入口查询，记录机构、版次年份、名次区间和访问日期。

更新后运行：

```powershell
python -m pytest tests\reference_data\test_university_references.py -q
python -m pytest tests\agents -q
ruff check src\reference_data src\agents\resume_review src\agents\batch_resume_review_llm tests
```

## GPU Stack 与图片生成智能体

工作区默认使用以下共享配置，真实 Key只放在 `.env.local`：

```env
GPU_STACK_BASE_URL=http://10.100.5.33:8003/v1
GPU_STACK_API_KEY=
```

现有 DeepSeek provider 默认使用 GPU Stack的 `deepseek-v4-flash`；各智能体
`*_BASE_URL`/`*_MODEL` 仍可覆盖。知识库问答默认使用 `deepseek-v4-flash`，
嵌入使用 `qwen3-vl-embedding-8b`。嵌入配置变化后必须显式重建：

```powershell
python -m src.knowledge_base ingest default --rebuild
```

图片智能体 dry-run：

```powershell
python -m src.agents.image_generation "画一只坐在窗边的猫" --dry-run
python -m src.agent_gateway dev --port 8008 --models image-generation-agent
```

当前环境由 WSL 自动配置的 `127.0.0.1:7897` HTTP代理访问 GPU Stack。
容器不能直接访问 WSL loopback；Compose 的 `gpu-stack-proxy-relay` sidecar
使用 host network，把仅绑定 Docker host-gateway的 `172.17.0.1:17897`
转发至 WSL 的 `127.0.0.1:7897`。worker默认通过
`GPU_STACK_CONTAINER_PROXY_URL` 选择代理。本机未提交的 `.env` 已配置：

```env
COMPOSE_PROFILES=local-proxy
GPU_STACK_CONTAINER_PROXY_URL=http://host.docker.internal:17897
```

因此本机 `docker compose up -d` 会自动启用并恢复 sidecar。服务器不需要7897
代理：不要复制本机 `.env`，不要启用 `local-proxy` profile，并保持
`GPU_STACK_CONTAINER_PROXY_URL` 为空，worker将直接访问 `GPU_STACK_BASE_URL`。
本机不要把 `10.100.5.33` 加入 `NO_PROXY`。

平台模型 ID为 `image-generation-agent`。无图片调用 `qwen-image`，有图片调用
`qwen-image-edit`；最近助手图片可作为下一轮默认底图。完整平台改造见
`docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`。

开启 `stream=true` 和 `thinking=true` 后，worker会立即通过
`delta.reasoning_content` 返回解析输入、模式选择、提示词改写结果和开始生成等
阶段，并在耗时生成期间每5秒发送当前阶段心跳。最终图片仍只在一次
`delta.content` 多模态数组中返回。这里的 thinking是执行进度，不包含模型隐藏
思维链。平台不显示 reasoning时可传 `"thinking": false`，进度将改走字符串
`delta.content`。

## ComfyUI 视频生成智能体

该 Agent 直接访问 ComfyUI，不需要启动独立 Videos API。先做不占用 GPU 的验证：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
$env:NO_PROXY = "localhost,127.0.0.1"
$env:COMFYUI_VIDEO_BASE_URL = "http://10.180.26.16:8188"
$env:COMFYUI_VIDEO_PUBLIC_BASE_URL = "http://10.180.26.16:8188"
python -m src.agents.comfyui_video_generation "生成5秒海边骑行视频，1280x720，25fps，随机种子42" --dry-run
python -m src.agent_gateway dev --port 8008 --models comfyui-video-generation-agent
```

`GET /health` 只有在 ComfyUI `/system_stats` 可用时返回 200；不可用时返回 503，统一网关将暂时隐藏该模型。正式 Chat Completion 支持 `stream`、`thinking`、`wait_for_completion`、`max_wait_seconds` 和显式 `video` 参数。

本机访问 `10.180.26.16` 需要经过 `127.0.0.1:7897` 代理，因此不能把
`10.180.0.0/16` 放入 `NO_PROXY`。Compose worker使用前文的
`GPU_STACK_CONTAINER_PROXY_URL=http://host.docker.internal:17897`，再由 relay转发到7897。
最终下载链接来自 `COMFYUI_VIDEO_PUBLIC_BASE_URL/view`，下载方也需要使用相同代理或具备
到该地址的直连路由。

按 `ai-app-platform` 后端调用上游模型的格式测试统一网关：

```powershell
python scripts/test_ai_app_video_agent.py `
  --base-url http://127.0.0.1:8008/v1 `
  --output cat.mp4
```

脚本默认模型为 `comfyui-video-generation-agent`，默认提示词为“生成一个猫咪视频”，不需要
应用ID或登录凭证。它直接调用 `/v1/chat/completions`，请求体和平台后端调用上游模型时一致，
覆盖统一网关、视频 Agent和ComfyUI；`--output` 可省略。只有设置了
`AGENT_GATEWAY_API_KEY` 时才需要传入可选的 `--api-key`。
