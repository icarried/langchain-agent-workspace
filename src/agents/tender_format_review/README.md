# 招标文件格式审查智能体

该智能体用于审查大型中文招标文件 `.docx` 的格式和跨章节一致性问题。它采用 LangGraph 工作流：

1. 解析 docx 段落和表格。
2. 按章节标题优先、长度兜底拆分。
3. 对每个片段执行 LLM 审查。
4. 汇总重复问题和跨章节复核项。
5. 输出 Markdown 审查报告。

## 为什么必须分块

招标文件可能超过 10 万字。DeepSeek 与 Qwen/DashScope 均存在随模型版本变化的上下文上限；即使选用长上下文模型，整篇一次审查也容易出现证据定位差、跨章节事项遗漏、失败后无法局部重试等问题。因此默认每块约 16000 字符，并保留重叠上下文。

当前模型接入策略：

- DeepSeek: 通过 OpenAI-compatible API，默认 `deepseek-v4-flash`，需要 `DEEPSEEK_API_KEY`。
- DashScope/Qwen: 通过 OpenAI-compatible API，默认 `qwen-plus`，需要 `DASHSCOPE_API_KEY`。
- 具体上下文上限应在运行前核对官方模型页；本智能体使用保守分块，不依赖单次超长上下文。

## 运行

默认审查规则位于 `src/agents/tender_format_review/review_guide/招标文件审查事项.md`。不传 `--review-guide` 时，CLI、API 和 MCP 会使用该默认指南，并自动合并同目录下的补充制度依据 Markdown。

```powershell
conda activate langchain
python -m src.agents.tender_format_review review `
  path\to\招标文件.docx `
  --review-guide C:\Users\Lenovo\Desktop\招标文件审查事项.md `
  --output 临时文件\招标文件格式审查报告.md `
  --provider deepseek
```

先验证解析和分块：

```powershell
python -m src.agents.tender_format_review review path\to\招标文件.docx --dry-run
```

## API 调用

启动 FastAPI 服务：

```powershell
uvicorn src.agents.tender_format_review.api:app --reload --port 8001
```

前端或编排工作流节点可调用：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8001/review `
  -ContentType "application/json" `
  -Body '{"docx_path":"./临时文件/仅包含一行文字的文件.docx","dry_run":true}'
```

也可以在本地编排节点中直接复用 Python 服务函数：

```python
from src.agents.tender_format_review import review_tender_format

result = review_tender_format("./临时文件/仅包含一行文字的文件.docx", dry_run=True)
```

## MCP 调用

MCP 是该智能体面向 Agent 编排的优先入口。客户端把待审 `.docx` 文件内容发送给 MCP 服务端，服务端临时落盘、执行审查，然后把 Markdown 报告作为 tool 返回值返回。调用方负责把返回的报告保存到自己的文件系统。

暴露的 tool：

```text
review_tender_format
```

tool 参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `docx_base64` | 是 | `.docx` 文件内容的 base64 字符串。 |
| `docx_filename` | 否 | 原始文件名，用于服务端临时文件名和返回元数据，默认 `uploaded.docx`。 |
| `dry_run` | 否 | 默认 `false`；建议连通性测试先传 `true`，避免调用付费模型。 |

MCP 接口不暴露 `review_guide_path`、`catalog_path`、`provider`、`model` 或 `output_path`。审查规则和模型选择属于智能体/服务端配置；参考目录不是必要输入；服务端只保存处理所需的临时文件，报告由 tool 返回给客户端。

### 本机 stdio 调用

stdio 模式通常由 MCP client 按需启动，不需要提前占用端口。手工启动命令：

```powershell
python -m src.agents.tender_format_review.mcp_server
```

最小 dry-run 参数形态：

```json
{
  "docx_filename": "待审招标文件.docx",
  "docx_base64": "<base64-encoded-docx>",
  "dry_run": true
}
```

### 内网 HTTP 调用

如需从内网其他机器调用，启动 HTTP MCP 常驻服务时不要只绑定 `127.0.0.1`，应绑定内网网卡：

```powershell
python -m src.agents.tender_format_review.mcp_server --transport http --host 0.0.0.0 --port 8002 --path /mcp
```

客户端连接地址使用 MCP 服务机器的内网 IP，例如：

```text
http://192.168.1.50:8002/mcp
```

HTTP MCP 不是普通 REST JSON 接口，不能直接用 `Invoke-RestMethod` 向 `/mcp` POST 业务 JSON；必须使用支持 MCP 的 client 或 SDK，例如 FastMCP client。

下面示例会把客户端本机的 `待审招标文件.docx` 发送给 HTTP MCP，并把返回的审查报告保存到客户端当前机器的 `reports/tender_review_report.md`。

```python
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main() -> None:
    transport = StreamableHttpTransport("http://192.168.1.50:8002/mcp")
    docx_path = Path(r"D:\待审文件\待审招标文件.docx")

    async with Client(transport) as client:
        result = await client.call_tool(
            "review_tender_format",
            {
                "docx_filename": docx_path.name,
                "docx_base64": base64.b64encode(docx_path.read_bytes()).decode("ascii"),
                "dry_run": False,
            },
        )

    report_path = Path("reports/tender_review_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result.data["report"], encoding="utf-8")
    print(f"saved: {report_path.resolve()}")
    print(f"filename: {result.data['filename']}")
    print(f"chunks: {result.data['chunk_count']}")


asyncio.run(main())
```

也可以使用仓库内脚本验证“发送文件内容 + 保存报告”流程：

```powershell
python scripts\call_tender_format_review_mcp.py `
  --transport http `
  --url http://192.168.1.50:8002/mcp `
  --docx-path D:\待审文件\待审招标文件.docx `
  --save-report reports\tender_review_report.md `
  --no-dry-run
```

返回字段包含 `report`、`dry_run`、`chunk_count` 和 `filename`。服务端不会把最终报告写到固定路径；如果调用方需要文件，应像上面的示例一样保存 `result.data["report"]`。

## 关键提示词

提示词位于 `prompts.py`：

- `CHUNK_REVIEW_SYSTEM` / `CHUNK_REVIEW_HUMAN`: 单片段审查。
- `AGGREGATE_SYSTEM` / `AGGREGATE_HUMAN`: 分块结果汇总。

## 输出原则

- 每条问题必须带证据位置，例如 `[paragraph#128]` 或 `[table#33]`。
- 明确区分“确定问题”“疑似问题”“需跨章节复核”。
- 对付款、验收、工期、承诺函、评分表、称呼等高风险事项优先汇总。
