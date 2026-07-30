# Handoff

用于 Agent 间交接。长任务结束、被中断或切换执行者时更新。

## 当前交接

- 2026-07-30 部门知识库批量导入、智能检索、DOC与来源下载:
  - 业务代码和本地验收已完成；用户已确认服务器部署，正在按不可变镜像流程发布并
    保留上一版本作为回滚点。
  - 提问链路新增 DeepSeek结构化查询改写、批量向量检索、RRF融合和证据回答；改写
    失败时回退原问题检索。参考 Dify DSL已提炼进计划，不依赖外部文件继续实施。
  - 用户来源只显示去重后的文档名，内部 chunk 引用继续保留但不再输出
    `#chunk-*`。
  - 下载收敛为“仅本次检索来源随回答返回既有 `delta.file`，AI应用平台复用现有
    `file_mapping` 和下载组件”；删除独立下载意图、按文件名下载和上一轮来源解析。
  - `thinking.txt` 证实旧流程保存 20 份文件时重新解析全部 449 份活动文档并生成
    3070 个向量；新发布流程复制活动 Chroma，只删除和重建本批发生变化的文档来源。
  - 所有保存创建卷内持久任务，默认上限 100；支持部分成功、断线继续、重启恢复已
    暂存文件和 `.doc` 临时转换解析。
  - AI应用平台只做必要的 `delta.file` 类型扩展和安全验证，不改上传、数据库或前端。
  - 完整规格见
    `docs/plans/2026-07-30-department-kb-batch-import-download-handoff.md`。
  - Agent 聚焦 46 项通过；全仓除两个缺失本地公文 golden输入外201项通过；平台
    后端全量、前端6项、TypeScript和Compose检查通过。
  - 本地容器已验证100附件受理、101附件前置拒绝、真实 DOC转换及平台 DOC/Markdown
    安全校验。平台只读端到端已验证查询改写、来源去重和 TXT `file_delta` 下载。

- 2026-07-24 图片生成平台交接:
  - 工作区新增 `image-generation-agent`，但 AI 应用平台必须增加多模态 content
    解析、MinIO持久化、`image_delta` SSE和助手图片附件回传，才能实现连续编辑。
  - 详细实施规格见 `docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`。

- 日期: 2026-07-14
- 状态: 统一入口已迁移至 `8008`；需要重新部署 Compose 后验证六个 worker 健康。
- 已完成:
  - 新增 `8008` 统一 OpenAI-compatible 网关、声明式六模型注册和健康过滤。
  - 新增本机 worker 监管器和根目录 Linux Docker Compose；worker 独立运行且只暴露内部 `8080`。
  - 将批量简历业务收敛到 `batch_resume_review_llm`，旧 `batch_resume_review` 包及其过时测试已移除。
  - 破坏性重做可复用知识库核心，按 namespace 和知识库名称隔离。
  - 共享远程附件安全下载和签名 Host 传输映射，移除招标智能体硬编码。
  - 146 项正式测试、全量 Ruff 及 Compose 故障隔离验收通过。
- 下一步建议:
  - FastGPT/Dify 统一改为 `http://<host>:8008/v1`，通过模型 ID 选择智能体。
  - 生产环境启用 `AGENT_GATEWAY_API_KEY` 并配置远程附件主机白名单。
