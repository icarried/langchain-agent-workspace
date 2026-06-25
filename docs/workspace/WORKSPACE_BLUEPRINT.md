# Workspace Blueprint

## 目标

把本目录建设成一个 Agent 友好的多智能体 LangChain / LangGraph 开发工作空间。任何 Agent 进入后，应能快速回答：

- 使用哪个 conda 环境。
- 真实密钥在哪里，变量名是什么。
- 源码、测试、文档、任务和问题分别放在哪里。
- 如何启动、调试、验证。
- 当前任务是什么，哪些任务已完成，哪些被阻塞。
- 当前有哪些智能体，分别在哪里，入口、依赖和调试方式是什么。

## 当前工作空间状态

- Conda 环境 `langchain` 已由用户创建完成。
- 后续运行和调试默认先执行 `conda activate langchain`。
- 工作空间预期承载多个智能体，不再按单一 Agent 项目组织。

## 信息放置约定

| 内容 | 路径 | 说明 |
| --- | --- | --- |
| Agent 入门规则 | `AGENTS.md` | 所有 Agent 优先阅读 |
| 工作空间说明 | `README.md` | 面向人和 Agent 的快速入口 |
| 任务台账 | `.agents/tasks/TASK_BOARD.md` | 任务拆分、状态、验收 |
| 交接记录 | `.agents/HANDOFF.md` | 长任务或换 Agent 时更新 |
| 环境搭建 | `docs/development/CONDA_LANGCHAIN_ENV.md` | conda 和依赖说明 |
| 启动调试 | `docs/development/RUN_AND_DEBUG.md` | 本地运行、调试、测试 |
| 密钥说明 | `docs/operations/SECRETS.md` | 变量名、来源、使用方式 |
| 问题日志 | `docs/operations/PROBLEM_LOG.md` | 问题、现象、定位、结论 |
| 决策记录 | `docs/workspace/DECISIONS.md` | 重要设计取舍 |
| 智能体登记表 | `docs/workspace/AGENT_REGISTRY.md` | 多智能体用途、路径、状态和运行入口 |
| 源码 | `src/` | LangChain / LangGraph 代码 |
| 测试 | `tests/` | 单元测试和集成测试 |

## 推荐源码结构

```text
src/
├── agents/          # 多个 Agent 的定义、图结构、执行入口
├── chains/          # LangChain chains 或 runnable 组合
├── tools/           # 工具函数和外部能力封装
├── memory/          # 记忆、状态、checkpoint 相关
├── prompts/         # prompt 模板
└── config/          # 配置加载、模型选择、环境变量读取
```

每个新增智能体建议使用 `src/agents/<agent_name>/`，并在 `docs/workspace/AGENT_REGISTRY.md` 登记。项目变大后再创建更多公共目录，避免空结构过多干扰。

## 搭建任务纲领

1. 建立 Agent 可读入口文档。
2. 建立任务台账和任务模板。
3. 整理密钥为 `.env.local` 和 `.env.example`。
4. 编写 LangChain / LangGraph conda 环境说明。
5. 编写启动、调试、测试说明。
6. 建立问题日志和决策记录。
7. 建立多智能体登记和目录规范。
8. 后续加入最小可运行 Agent 示例。
9. 后续加入测试样例和 CI 或本地验证命令。
