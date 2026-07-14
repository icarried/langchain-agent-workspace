# LangChain Knowledge Base Agent

本目录只保留知识库智能体的 OpenAI-compatible / 管理 API 适配层。可复用核心位于
`src/knowledge_base/`，所有数据按 `namespace/knowledge-base-name` 隔离。

默认数据目录：

```text
data/knowledge_bases/langchain-knowledge-base-agent/default/
├── documents/
├── chroma/
└── manifest.json
```

把文档放入 `documents/` 后调用内部接口：

```text
POST /v1/knowledge-bases/default/ingest
POST /v1/knowledge-bases/default/retrieval
```

生产环境通过根目录 `compose.yaml` 启动；OpenAI 调用统一使用网关
`http://<host>:8008/v1` 和模型 `langchain-knowledge-base-agent`。

平台配置时启用流式输出；生产启用鉴权时发送
`Authorization: Bearer <AGENT_GATEWAY_API_KEY>`。若调用方位于 Docker 容器，
`127.0.0.1` 是调用方自身而不是网关。当前 `ai-app-platform` backend 已验证
`http://172.27.0.1:8008/v1`；长期推荐在共享 Docker 网络中使用
`http://gateway:8008/v1`。完整部署说明见 `docs/development/AGENT_GATEWAY.md`。

知识库管理接口只在 worker 内部使用，不由首版网关公开。通过
`KB_DATA_ROOT`、`KB_NAMESPACE`、`KB_DEFAULT_NAME`、模型/API 配置、`KB_TOP_K`
和 `KB_MIN_RELEVANCE_SCORE` 配置；不要恢复旧 primary/secondary 配置或共享
Chroma collection。新智能体直接复用 `KnowledgeBaseManager(namespace)` 并使用自己的安全 slug namespace。
