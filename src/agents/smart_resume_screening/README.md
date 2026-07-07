# smart-resume-screening

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

正式调用 DeepSeek 时去掉 `--dry-run`；也可用 `--provider dashscope --model qwen-plus` 调用 Qwen。

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

## 环境变量

- `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`
- 可选 `SMART_RESUME_SCREENING_MODEL`
- 可选 `SMART_RESUME_SCREENING_BASE_URL`

## 与现有批量简历智能体的区别

`batch-resume-review` 更适合完整招聘流程、OCR、远程 URL、学历高校参照和复杂报告；本智能体更像 FastGPT 中的结构化初筛配置器，适合快速验证岗位条件、候选人排名和筛选口径。

