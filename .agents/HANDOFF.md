# Handoff

用于 Agent 间交接。长任务结束、被中断或切换执行者时更新。

## 当前交接

- 日期: 2026-07-14
- 状态: 统一入口已迁移至 `8008`；需要重新部署 Compose 后验证六个 worker 健康。
- 已完成:
  - 新增 `8008` 统一 OpenAI-compatible 网关、声明式六模型注册和健康过滤。
  - 新增本机 worker 监管器和根目录 Linux Docker Compose；worker 独立运行且只暴露内部 `8080`。
  - 将批量简历业务收敛到 `batch_resume_review_llm`，旧包只保留兼容转发。
  - 破坏性重做可复用知识库核心，按 namespace 和知识库名称隔离。
  - 共享远程附件安全下载和签名 Host 传输映射，移除招标智能体硬编码。
  - 146 项正式测试、全量 Ruff 及 Compose 故障隔离验收通过。
- 下一步建议:
  - FastGPT/Dify 统一改为 `http://<host>:8008/v1`，通过模型 ID 选择智能体。
  - 生产环境启用 `AGENT_GATEWAY_API_KEY` 并配置远程附件主机白名单。
