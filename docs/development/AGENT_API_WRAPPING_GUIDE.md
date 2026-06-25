# Agent API Wrapping Guide

本指引用于把 `src/agents/<agent_name>/` 下的智能体封装成可被前端或编排工作流节点调用的 API。

## 推荐结构

```text
src/agents/<agent_name>/
├── api.py       # FastAPI app、请求模型、响应模型
├── service.py   # 可复用业务入口，CLI 和 API 共用
├── cli.py       # 命令行入口，只负责参数解析和展示
└── graph.py     # LangGraph 工作流
```

## 封装步骤

1. 先从 CLI 或旧入口中抽出服务函数，例如 `run_agent(...)`。
2. 服务函数负责路径解析、模型创建、图调用和响应整理，不依赖 FastAPI。
3. API 层只定义 `BaseModel` 请求/响应和 HTTP 路由，避免复制图调用逻辑。
4. 对文件路径统一支持工作空间相对路径；前端可传 `./临时文件/example.docx`。
5. 长文档、付费模型或慢任务必须保留 `dry_run`，用于快速验证解析、分块和输出路径。
6. 响应中返回可编排字段，例如 `report`、`output_path`、`chunk_count`、`chunks`、`provider`、`model`。
7. 保留 Python 服务函数，编排工作流既可以走 HTTP，也可以作为本地节点直接 import 调用。

## FastAPI 约定

- `GET /health`: 返回智能体名称和服务状态。
- `POST /review` 或领域动作路径: 执行智能体主流程。
- 请求模型命名为 `<AgentAction>Request`。
- 响应模型命名为 `<AgentAction>Response`。
- 不在 API 层读取真实密钥；模型 provider 仍使用 `.env.local` 中的变量。

## 测试约定

- 至少测试服务函数 dry-run。
- 至少测试 API health 和主接口 dry-run。
- 大文件智能体使用最小样例文件测试，避免完整业务文件拖慢验证。
- 如果需要真实模型调用，应单独记录命令，不作为默认单元测试。

## tender-format-review 示例

启动 API：

```powershell
conda activate langchain
uvicorn src.agents.tender_format_review.api:app --reload --port 8001
```

调用 dry-run：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8001/review `
  -ContentType "application/json" `
  -Body '{"docx_path":"./临时文件/仅包含一行文字的文件.docx","dry_run":true}'
```

本地编排节点直接调用：

```python
from src.agents.tender_format_review import review_tender_format

result = review_tender_format(
    "./临时文件/仅包含一行文字的文件.docx",
    dry_run=True,
)
```
