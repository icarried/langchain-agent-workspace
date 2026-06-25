# Source Layout

这里放多个 LangChain / LangGraph 智能体源码。

建议随项目增长逐步建立：

```text
src/
├── agents/
├── chains/
├── tools/
├── memory/
├── prompts/
└── config/
```

当前优先保持结构轻量。新增智能体时建议：

- 在 `src/agents/<agent_name>/` 下放该智能体的图、入口、prompt 和专属工具。
- 在 `docs/workspace/AGENT_REGISTRY.md` 登记该智能体。
- 在 `.agents/tasks/TASK_BOARD.md` 登记创建或修改任务。
- 在 `docs/development/RUN_AND_DEBUG.md` 追加该智能体的启动和调试方式。
