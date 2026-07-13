# contract-review

`contract-review` 是根据 FastGPT 导出工作流“合同审查大师”的有效经验转化而来的 LangChain / LangGraph 智能体。它不照抄 FastGPT 节点，而是保留其中更适合复用的设计：表单化收集委托方角色、合同类型和交易背景，按六个维度并行审查，再生成评分评级和整改建议。

## 能力范围

- 支持本地 DOCX、文本型 PDF、TXT、MD 合同解析。
- 按章节或长度分块，保留元素编号作为证据引用。
- 六维审查：主体合法性、内容合法性、条款完备性与明确性、风险防控与实用性、形式与表述规范、履行与终止。
- 输出 0-100 分、A/B/C/D 评级、风险清单、修改建议和待补充资料。
- 支持 CLI、REST API 和 MCP；支持 `--dry-run` 验证解析和工作流，不调用模型。

## CLI

```powershell
python -m src.agents.contract_review review `
  src\agents\contract_review\examples\示例服务合同.md `
  --client-role 甲方 `
  --contract-type 技术服务合同 `
  --transaction-background "甲方采购设备运行数据分析平台开发服务" `
  --output 临时文件\合同审查_dry_run.md `
  --dry-run
```

正式调用 DeepSeek 时去掉 `--dry-run`；也可用 `--provider dashscope --model qwen-plus` 调用 Qwen。

## API

```powershell
uvicorn src.agents.contract_review.api:app --reload --port 8009
```

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8009/review `
  -ContentType "application/json" `
  -Body '{"contract_path":"src/agents/contract_review/examples/示例服务合同.md","client_role":"甲方","contract_type":"技术服务合同","transaction_background":"采购数据分析平台","dry_run":true}'
```

## MCP

stdio:

```powershell
python -m src.agents.contract_review.mcp_server
```

HTTP:

```powershell
python -m src.agents.contract_review.mcp_server --transport http --host 127.0.0.1 --port 8009 --path /mcp
```

Tool 名称为 `review_contract`，接收 `contract_base64`、`contract_filename`、`client_role`、`contract_type`、`transaction_background` 和 `dry_run`。

## OpenAI-compatible LLM

```powershell
uvicorn src.agents.contract_review.openai_compatible_api:app --host 0.0.0.0 --port 8014
```

模型 ID 为 `contract-review-agent`。提示词仍推荐使用 `合同文件：` 区块；也兼容平台自动生成的 `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url` / `image_url.url`。

```text
委托方角色：甲方
合同类型：技术服务合同
交易背景：甲方采购设备运行数据分析平台开发服务

附件：
- 服务合同.docx: http://minio.example/service-contract.docx?X-Amz-Signature=...

输出要求：请输出合同审查报告。
```

URL 必须能被智能体服务所在环境访问；若使用 MinIO 预签名 URL，不要使用服务进程无法访问的 `localhost`。

## 环境变量

- `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`
- 可选 `CONTRACT_REVIEW_MODEL`
- 可选 `CONTRACT_REVIEW_BASE_URL`

## 边界

第一版不处理扫描 PDF OCR、外部法律知识库检索、自动红线批注和合同全文改写。本报告为辅助审查，不替代执业律师正式法律意见。
