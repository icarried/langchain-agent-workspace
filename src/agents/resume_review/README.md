# Resume Review Agent

`resume-review` 是人力部门简历审查智能体，运行时支持 DOCX、文本型 PDF 和 TXT 简历。它输出 Markdown 报告，覆盖基本条件与注入风险、筛选条件与学历时间线、专业条件与岗位匹配。

`examples/` 下的 Markdown 文件只是便于维护和重复执行的测试夹具。MCP 调用协议不使用 Markdown：岗位要求通过 `job_description_text` 传入，简历以 DOCX/PDF/TXT 文件内容的 base64 传入。

第一版不支持扫描件 OCR。岗位 JD 是可选输入：提供 JD 时输出匹配评分；未提供 JD 时报告会写明“未提供 JD，岗位匹配未评分”。

提示词注入由确定性规则检测，一经发现报告明确给出“筛除”；技能熟练程度只影响匹配分。学历仅在 JD 明确最低学历要求时作为硬性门槛。

## 审查事项

审查规则位于 `review_guide/`，按维度拆分：

- `基本条件与注入风险.md`: 区分招聘要求和简历内容，提取“忽略前面的内容”“强制设定为通过”等提示词注入或异常文本。
- `筛选条件与学历时间线.md`: 分析学校层次、独立学院和二级学院差异、本科/研究生在校时间、毕业与工作时间线衔接。
- `专业条件与岗位匹配.md`: 分析专业、工作经验、项目、校招 GPA/竞赛/奖学金/论文等与岗位的匹配程度。

正式模型审查会按这些维度并行检查，再由汇总节点合并报告。

## 高校参考资料

正式审查默认加载 `src/reference_data/universities/`。其中 985/211 使用教育部固定历史名单，双一流文件带轮次和年份；“一本”和世界大学排名按文件中的动态查询规则核验，不允许模型凭记忆给出当前排名。

## CLI

```powershell
python -m src.agents.resume_review review path\to\resume.pdf `
  --job-description path\to\jd.txt `
  --output 临时文件\简历审查报告.md `
  --dry-run
```

使用内置“人工智能开发工程师”测试样例：

```powershell
python -m src.agents.resume_review review `
  src\agents\resume_review\examples\示例简历_人工智能开发工程师.md `
  --job-description src\agents\resume_review\examples\人工智能开发工程师岗位要求.md `
  --provider deepseek --model deepseek-v4-flash `
  --output 临时文件\简历审查_人工智能开发工程师_deepseek-v4-flash.md
```

正式调用 DeepSeek：

```powershell
python -m src.agents.resume_review review path\to\resume.docx `
  --job-description path\to\jd.txt `
  --provider deepseek
```

正式调用 DashScope/Qwen：

```powershell
python -m src.agents.resume_review review path\to\resume.txt `
  --job-description path\to\jd.txt `
  --provider dashscope --model qwen-plus
```

## API

启动：

```powershell
uvicorn src.agents.resume_review.api:app --reload --port 8004
```

调用 dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8004/review `
  -ContentType "application/json" `
  -Body '{"resume_path":"./临时文件/sample_resume.txt","job_description_text":"招聘 Python 后端工程师","dry_run":true}'
```

## MCP

启动 stdio MCP server：

```powershell
python -m src.agents.resume_review.mcp_server
```

HTTP MCP：

```powershell
python -m src.agents.resume_review.mcp_server --transport http --host 127.0.0.1 --port 8003 --path /mcp
```

MCP tool 名称为 `review_resume`，参数为：

```json
{
  "resume_base64": "<base64 encoded docx/pdf/txt>",
  "resume_filename": "candidate.pdf",
  "job_description_text": "岗位 JD 文本",
  "dry_run": true
}
```

这里的 Markdown 只指返回报告格式；上传简历格式限定为 DOCX、文本型 PDF 或 TXT。

## 环境变量

- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- 可选：`RESUME_REVIEW_MODEL`
- 可选：`RESUME_REVIEW_BASE_URL`
