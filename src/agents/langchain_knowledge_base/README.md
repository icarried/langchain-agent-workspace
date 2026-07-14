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
`http://<host>:8004/v1` 和模型 `langchain-knowledge-base-agent`。
