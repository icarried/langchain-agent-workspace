# Agent MCP Wrapping Guide

本指引用于把 `src/agents/<agent_name>/` 下的 LangChain / LangGraph 智能体封装成 MCP server。相比 HTTP API，MCP 更适合作为 Agent 编排、Codex/Claude Desktop 等客户端的工具节点入口。

## 推荐结构

```text
src/agents/<agent_name>/
├── mcp_server.py  # FastMCP server 和 tool 定义
├── service.py     # 可复用业务入口，CLI/API/MCP 共用
├── api.py         # 可选 HTTP API
├── cli.py         # 可选命令行入口
└── graph.py       # LangGraph 工作流
```

## 封装原则

1. 先抽 `service.py`，把路径解析、模型创建、图调用和响应整理放在服务函数中。
2. MCP tool 只做参数声明和服务函数转发，不复制 LangGraph 调用逻辑。
3. tool 名称使用稳定动词短语，例如 `review_tender_format`、`summarize_contract`。
4. 参数保持可编排：路径、provider、model、dry_run、output_path 等都显式暴露。
5. 文件路径默认支持工作空间相对路径，例如 `./临时文件/example.docx`。
6. 长文档、付费模型或慢任务必须提供 `dry_run`，用于 MCP client 连通性和解析测试。
7. 返回结构化字典，至少包含核心结果、输入文件绝对路径、模型信息、dry_run 状态和可追踪元数据。
8. MCP 是后续 Agent 编排优先入口；HTTP API 可作为前端或非 MCP 系统的补充入口。

## FastMCP 模板

```python
from typing import Any

from fastmcp import FastMCP

from .service import run_agent

mcp = FastMCP(
    name="agent-name",
    instructions="Describe when and how MCP clients should call this agent.",
)


@mcp.tool(name="run_agent", description="Run the agent.")
def run_agent_tool(input_path: str, dry_run: bool = False) -> dict[str, Any]:
    return run_agent(input_path, dry_run=dry_run)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## MCP 客户端配置示例

## stdio 与 HTTP 怎么选

MCP 本身是工具协议，常见传输方式有 stdio 和 HTTP。

| 方式 | 是否需要提前起服务 | 谁负责启动 | 适合场景 |
| --- | --- | --- | --- |
| stdio | 不需要 | MCP client 按配置启动子进程 | 本机 Agent 编排、Codex/Claude Desktop、本地工具节点 |
| HTTP / streamable HTTP | 需要 | 你先启动常驻 MCP 服务 | 跨进程、跨机器、Web 编排器、多个客户端共享 |

推荐默认使用 stdio。它不是常驻端口服务，MCP client 看到配置后会按需启动命令，通过标准输入/输出通信。HTTP 形式更像传统服务，需要先运行 server，客户端通过 URL 连接。

## stdio 接入

MCP client 配置示例：

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

调用时，客户端会发现 tool `review_tender_format`，然后传入参数：

```json
{
  "docx_path": "./临时文件/仅包含一行文字的文件.docx",
  "dry_run": true
}
```

Python 测试调用示例：

```python
import asyncio
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "src.agents.tender_format_review.mcp_server"],
        cwd="E:\\My_sorcode\\--创建智能体工作空间--",
    )
    async with Client(transport) as client:
        result = await client.call_tool(
            "review_tender_format",
            {
                "docx_path": "./临时文件/仅包含一行文字的文件.docx",
                "dry_run": True,
            },
        )
        print(result.data["chunk_count"])


asyncio.run(main())
```

本工作空间也提供了可直接运行的 stdio 调用脚本：

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts\call_tender_format_review_mcp.py --transport stdio
```

## HTTP 接入

先启动常驻 MCP HTTP server：

```powershell
conda activate langchain
python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp
```

Windows + Codex 沙箱下，如果后台运行 `conda run -n langchain ...` 出现 `Access is denied`、找不到 `__conda_tmp_*.txt`，或导入外部 conda 环境包时触发权限问题，优先直接调用目标环境解释器。该工作区已验证以下方式可启动常驻 HTTP MCP：

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

MCP client 连接 URL：

```text
http://127.0.0.1:8002/mcp
```

Python 测试调用示例：

```python
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main() -> None:
    transport = StreamableHttpTransport("http://127.0.0.1:8002/mcp")
    async with Client(transport) as client:
        result = await client.call_tool(
            "review_tender_format",
            {
                "docx_path": "./临时文件/仅包含一行文字的文件.docx",
                "dry_run": True,
            },
        )
        print(result.data["chunk_count"])


asyncio.run(main())
```

本工作空间也提供了可直接运行的 HTTP 调用脚本：

```powershell
$env:PYTHONIOENCODING='utf-8'
C:\Users\Lenovo\.conda\envs\langchain\python.exe scripts\call_tender_format_review_mcp.py --transport http --url http://127.0.0.1:8002/mcp
```

Windows 中文路径下建议先设置 `PYTHONIOENCODING=utf-8`，避免 `conda run` 输出阶段出现 GBK 编码错误。

注意：HTTP MCP 不是普通 REST API。不要用 `Invoke-RestMethod` 直接向 `/mcp` POST 业务 JSON；应使用支持 MCP 的 client 或 SDK。

## 测试约定

- 使用 `fastmcp.Client(mcp)` 做 in-process 测试，不需要真正启动子进程。
- 测试至少覆盖 `list_tools()` 能发现目标 tool。
- 测试至少调用一次 dry-run tool。
- 大文件智能体使用最小样例文件测试，避免默认测试调用完整业务文件。

## tender-format-review 示例

启动 MCP server：

```powershell
conda activate langchain
python -m src.agents.tender_format_review.mcp_server
```

这会以 stdio 方式运行，通常由 MCP client 按需启动。手工运行时终端会被该进程占用，等待 MCP client 通过 stdio 通信。

如需 HTTP MCP：

```powershell
python -m src.agents.tender_format_review.mcp_server --transport http --host 127.0.0.1 --port 8002 --path /mcp
```

如果是让 Agent 在后台起常驻服务，优先使用上文的 `C:\Users\Lenovo\.conda\envs\langchain\python.exe` + `Start-Process` 方式，并检查 `临时文件\tender_format_review_mcp.err.log`。2026-06-17 已验证该方式能启动 `http://127.0.0.1:8002/mcp`，并通过 HTTP MCP dry-run 返回 `chunk_count=1`。

MCP tool 名称：

```text
review_tender_format
```

最小 dry-run 参数：

```json
{
  "docx_path": "./临时文件/仅包含一行文字的文件.docx",
  "dry_run": true
}
```
