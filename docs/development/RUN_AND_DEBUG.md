# Run And Debug

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

- Base URL: `http://<服务地址>:8007/v1`
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

`招标文件` 也可以是服务端本地 `.docx` 路径。FastGPT 文件变量渲染为 JSON 数组时，服务会读取数组中的第一个文件链接。远程 `.docx` 会临时下载后交给原 `review_tender_format` 服务层；可用 `TENDER_REVIEW_MAX_REMOTE_FILE_BYTES` 和 `TENDER_REVIEW_REMOTE_TIMEOUT_SECONDS` 调整大小上限和超时。

当前存在一处临时 MinIO 传输映射：FastGPT 生成的预签名 URL 为 `10.71.2.94:9000`，但 Windows 侧实际访问该实例需要走 `127.0.0.1:9002`。`src.agents.tender_format_review.openai_compatible_api` 会在读取远程 `.docx` 时把实际连接地址映射为 `127.0.0.1:9002`，同时保留原始 `Host: 10.71.2.94:9000` 和完整查询签名。该逻辑只用于这个具体地址，是临时兼容层；修好 FastGPT/MinIO 外部签名地址后应删除。

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
uvicorn src.agents.resume_review.api:app --reload --port 8004
```

用文本简历测试 API dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8004/review `
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

## 批量简历审查与排序智能体

使用多份本地测试夹具执行 dry-run：

```powershell
python -m src.agents.batch_resume_review review `
  src\agents\batch_resume_review\examples\候选人A_工业AI.md `
  src\agents\batch_resume_review\examples\候选人B_条件不符.md `
  src\agents\batch_resume_review\examples\候选人C_待确认.md `
  --job-description src\agents\batch_resume_review\examples\人工智能开发工程师岗位要求.md `
  --output 临时文件\批量简历审查_dry_run.md `
  --dry-run
```

正式调用时去掉 `--dry-run`，可用 `--provider` 和 `--model` 覆盖服务端默认模型。提示词注入和明确不满足学历等硬条件者输出筛除理由且不参与排名；证据不足、学制或时间线待核验者仍参与 0-100 分排序，并在“附加复核项”中重复显示。技能熟练程度只影响分数，不作为硬筛。

启动 API：

```powershell
uvicorn src.agents.batch_resume_review.api:app --reload --port 8006
```

API 的 `resume_paths` 可混合使用服务端本地路径与 FastGPT/MinIO HTTP(S) 预签名 URL。岗位要求正文传给 `job_description_text`；服务端岗位文件路径传给 `job_description_path`。生产内网建议设置 `BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS=10.71.2.94`，远程文件默认上限 10 MiB、超时 30 秒。

若 FastGPT 预签名 URL 使用 `10.71.2.94:9000`，但其 MinIO 实际发布为宿主机 `9002 -> 容器 9000`，设置 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT=http://127.0.0.1:9002` 后重启 API。下载连接走 9002，签名 Host 仍保持 9000。

启动 stdio 或 HTTP MCP：

```powershell
python -m src.agents.batch_resume_review.mcp_server
python -m src.agents.batch_resume_review.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp
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
python scripts\package_agent_standalone.py --agent batch_resume_review --output-dir dist
```

ZIP 内的 `README.md` 包含独立安装、CLI、API、stdio/HTTP MCP 使用说明；`mcp-config.example.json` 和 `mcp_client_example.py` 可直接改路径后使用。通用封装约定见 `docs/development/AGENT_STANDALONE_PACKAGING_GUIDE.md`。

## 批量简历 OpenAI-compatible 流式适配智能体

`batch-resume-review-llm` 是从 `batch-resume-review` 复制隔离出来的新智能体，供 Dify/FastGPT 自定义 OpenAI-compatible LLM 节点调用。它和原智能体沿用相同端口，不要同时启动。

面向 FastGPT、Dify 等平台的人读版接入说明见 `docs/development/OPENAI_COMPATIBLE_LLM_PLATFORM_INTEGRATION.md`。

启动 OpenAI-compatible 服务：

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

模型配置：

- Base URL: `http://<服务地址>:8006/v1`
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
ruff check src\reference_data src\agents\resume_review src\agents\batch_resume_review tests
```
