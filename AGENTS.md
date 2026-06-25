# Agent Operating Guide

本文件是 Agent 进入该工作空间后的第一阅读文件。目标是让任何 Agent 都能快速进入开发、定位问题、拆分任务并留下可接续的记录。

## 工作原则

- 先读文档，再改代码。优先阅读 `README.md`、本文件、`docs/workspace/WORKSPACE_BLUEPRINT.md` 和当前任务。
- 任务必须可确认完成。每个任务应有目标、验收标准、状态和最后更新记录。
- 不泄露密钥。真实密钥只放在 `.env.local` 或 `secrets/` 下，文档只写变量名和用途。
- 发现问题要沉淀。无法立即修复的问题记录到 `docs/operations/PROBLEM_LOG.md`。
- 变更要可复盘。重要设计取舍记录到 `docs/workspace/DECISIONS.md`。
- 尽量保持小步提交和小范围修改。不要重构与任务无关的内容。

## 推荐工作流

1. 阅读 `.agents/tasks/TASK_BOARD.md`，选择 `Ready` 或用户指定任务。
2. 在任务条目中补充执行计划和验收标准。
3. 阅读相关目录和文档，确认环境变量、启动方式和测试方式。
4. 实现或修复。
5. 运行最小必要验证。
6. 更新任务状态、问题日志、决策记录或运行手册。

## 任务状态

- `Backlog`: 想做但还未准备开始。
- `Ready`: 信息足够，可以开始。
- `In Progress`: 正在处理。
- `Blocked`: 被外部条件阻塞，需要说明原因。
- `Review`: 已完成实现，等待检查或确认。
- `Done`: 满足验收标准。

## 开发入口

- Conda 环境: `docs/development/CONDA_LANGCHAIN_ENV.md`
- 启动与调试: `docs/development/RUN_AND_DEBUG.md`
- 密钥管理: `docs/operations/SECRETS.md`
- 问题日志: `docs/operations/PROBLEM_LOG.md`

