# Agent Registry

用于登记本工作空间中的多个智能体。每新增一个智能体，都应在这里记录用途、路径、入口、依赖和当前状态，方便人和 Agent 快速接手。

## 登记规则

- 每个智能体使用一个稳定名称，建议小写英文和短横线，例如 `research-agent`。
- 源码建议放在 `src/agents/<agent_name>/`。
- 启动和调试方式应同步写入 `docs/development/RUN_AND_DEBUG.md`。
- 相关任务应同步写入 `.agents/tasks/TASK_BOARD.md`。
- 不在本文件记录真实 API key，只记录需要的环境变量名。

## 智能体列表

### batch-resume-review

- 状态: Ready
- 用途: 一次审查多份 PDF、DOC、DOCX、MD 或 TXT 简历，强制筛除提示词注入和明确硬条件不符者，对其余候选人统一评分排序，并附加人工复核标记。
- 源码路径: `src/agents/batch_resume_review/`
- 运行入口: `python -m src.agents.batch_resume_review review <resume-a> <resume-b> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.batch_resume_review.mcp_server`；HTTP `python -m src.agents.batch_resume_review.mcp_server --transport http --host 127.0.0.1 --port 8005 --path /mcp`；tool 名称 `review_resumes`。
- API 入口: `uvicorn src.agents.batch_resume_review.api:app --reload --port 8006`，主接口 `POST /review`。
- 调试方式: 先用多份本地测试夹具运行 `--dry-run`，再接入模型验证筛除和排序；MCP 接收 `resumes` 文件列表和 `job_description_text`。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `BATCH_RESUME_REVIEW_MODEL`、`BATCH_RESUME_REVIEW_BASE_URL`、`BATCH_RESUME_REVIEW_ALLOWED_URL_HOSTS`、`BATCH_RESUME_REVIEW_MAX_REMOTE_FILE_BYTES`、`BATCH_RESUME_REVIEW_REMOTE_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MODEL`、`BATCH_RESUME_REVIEW_OCR_BASE_URL`、`BATCH_RESUME_REVIEW_OCR_TIMEOUT_SECONDS`、`BATCH_RESUME_REVIEW_OCR_MAX_PAGES`。
- 独立打包: `python scripts/package_agent_standalone.py --agent batch_resume_review --output-dir dist`，产物可脱离工作区运行。
- 关联任务: T-016、T-019、T-022、T-023
- 备注: REST API 的 `resume_paths` 支持服务端路径和 MinIO HTTP(S) 预签名 URL，并对远程读取实施超时、大小上限和可选主机白名单。筛除名单不参与排名，待复核候选人保留排名并同时出现在复核项中。报告显示简历原文姓名和文件名。CLI/API/MCP 均接受 PDF/DOC/DOCX/MD/TXT；扫描件按需使用百炼 OCR。正式审查加载智能体包内 `references/universities/` 高校参照。

### resume-review

- 状态: Ready
- 用途: 审查人力部门收到的 DOCX、文本型 PDF 和 TXT 简历，输出基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配评分和面试追问建议。
- 源码路径: `src/agents/resume_review/`
- 运行入口: `python -m src.agents.resume_review review <resume> --job-description <jd.txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.resume_review.mcp_server`；HTTP `python -m src.agents.resume_review.mcp_server --transport http --host 127.0.0.1 --port 8003 --path /mcp`；tool 名称 `review_resume`。
- API 入口: `uvicorn src.agents.resume_review.api:app --reload --port 8004`，主接口 `POST /review`。
- 调试方式: 先运行 `--dry-run` 验证简历解析、分块和 JD 输入，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `RESUME_REVIEW_MODEL`、`RESUME_REVIEW_BASE_URL`。
- 关联任务: T-015
- 备注: 第一版支持文本型 PDF，不支持扫描件 OCR；岗位 JD 可选，未提供 JD 时不生成匹配分，避免伪造岗位匹配依据。审查事项按 Markdown 文件拆分，正式 LLM 审查按基本条件/筛选条件/专业条件三个维度并行调用后汇总；学历维度默认加载 `src/reference_data/universities/` 高校参照。

### tender-format-review

- 状态: Ready
- 用途: 审查大型中文招标文件 `.docx` 的格式、章节、表格和跨章节一致性问题，输出 Markdown 审查报告。
- 源码路径: `src/agents/tender_format_review/`
- 运行入口: `python -m src.agents.tender_format_review review <docx> --review-guide <md> --catalog <txt> --output <report.md>`
- MCP 入口: stdio `python -m src.agents.tender_format_review.mcp_server`；HTTP `python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp`；tool 名称 `review_tender_format`。
- API 入口: `uvicorn src.agents.tender_format_review.api:app --reload --port 8001`，主接口 `POST /review`。
- 调试方式: 先运行 `--dry-run` 验证 docx 解析、分块和输出路径，再接入 DeepSeek 或 DashScope/Qwen 模型。
- 需要的环境变量: `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`；可选 `TENDER_REVIEW_MODEL`、`TENDER_REVIEW_BASE_URL`。
- 关联任务: T-009、T-011、T-012
- 备注: 对 10 万字以上文件默认采用“解析元素 -> 章节/长度分块 -> 分块审查 -> 汇总复核”，不依赖整篇一次放入上下文。Codex 后台起常驻 HTTP MCP 时，优先直接调用 `C:\Users\Lenovo\.conda\envs\langchain\python.exe`，不要依赖 `conda run`；详见 `docs/development/RUN_AND_DEBUG.md` 和 `docs/operations/PROBLEM_LOG.md` 的 2026-06-17 记录。

## 模板

```text
### <agent_name>

- 状态: Planned / In Development / Ready / Deprecated
- 用途:
- 源码路径: `src/agents/<agent_name>/`
- 运行入口:
- 调试方式:
- 需要的环境变量:
- 关联任务:
- 备注:
```
