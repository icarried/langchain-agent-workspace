# 多智能体统一网关

统一网关是所有 OpenAI-compatible 智能体的推荐入口。对外只发布 `8008`，调用方通过请求体中的 `model` 选择智能体；各智能体 worker 独立运行，单个 worker 停止不会带崩网关或其他模型。

## 平台接入

FastGPT、Dify 或其他 OpenAI-compatible 客户端统一配置：

```text
Base URL: http://<host>:8008/v1
API Key: <AGENT_GATEWAY_API_KEY；未启用鉴权时可填占位值>
Stream: enabled
```

当前模型 ID：

- `batch-resume-review-agent`
- `tender-format-review-agent`
- `smart-resume-screening-agent`
- `contract-review-agent`
- `official-document-review-agent`
- `langchain-knowledge-base-agent`
- `department-knowledge-base-agent`
- `image-generation-agent`

`GET /v1/models` 只返回当前健康、可调用的模型。未知模型返回 `404 model_not_found`；已登记但不可用的模型返回 `503 model_unavailable`。`GET /health` 返回网关和各 worker 的脱敏状态。

生产环境应设置 `AGENT_GATEWAY_API_KEY`。请求使用 `Authorization: Bearer <key>`；默认不设置时关闭鉴权，以兼容现有平台。

## 本机开发

```powershell
python -m src.agent_gateway dev --port 8008
python -m src.agent_gateway dev --port 8008 --models batch-resume-review-agent,contract-review-agent
```

启动器为 worker 自动选择回环端口，异常退出后按 1、2、5、10、30 秒上限退避重启，按 Ctrl+C 会清理全部子进程。旧 `resume-review` REST API 如需单独调试，必须显式选择非 `8008` 端口。

## Docker Compose 生产部署

本机 Docker 由 WSL `Ubuntu` 管理。先确认路径与身份：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/My_sorcode/--创建智能体工作空间-- && pwd && whoami && docker compose config --quiet'
```

构建并启动：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/My_sorcode/--创建智能体工作空间-- && DOCKER_BUILDKIT=0 docker compose build gateway && docker compose up -d'
```

当前 Windows 挂载路径含中文时，BuildKit 会因会话共享键头包含非 ASCII 字符而失败，因此使用传统构建器；项目迁移到纯 ASCII Linux 路径后可重新验证 BuildKit。

Compose 仅把 gateway 发布为 `8008:8008`；worker 只在 Compose 网络内监听 `8080`，并通过服务 DNS 寻址。停止服务使用 `docker compose down`。不要执行 `docker compose down -v`，除非明确要删除知识库持久化卷和部门原件 MinIO 卷。

故障隔离验收：

```bash
python3 scripts/verify_agent_gateway_isolation.py
```

脚本会停止并恢复 `contract-review` worker，动态记录模型总数，验证其模型从列表移除、
其他模型仍可调用、恢复后全部模型重新可见。

机器人管理平台服务器的离线镜像发布、生产密钥、`10085:8008` 端口、升级和回滚
流程见 `docs/operations/ROBOT_PLATFORM_DOCKER_DEPLOYMENT.md`。

## 远程附件

文件型智能体支持本地挂载路径、HTTP(S) URL、FastGPT `附件：` 列表，以及 OpenAI content parts 中的 `file_url.url`、`image_url.url`。预签名 MinIO/S3 URL 的查询参数不会被重写。

生产环境应配置 `AGENT_REMOTE_ALLOWED_HOSTS`、`AGENT_REMOTE_MAX_BYTES` 和 `AGENT_REMOTE_TIMEOUT_SECONDS`。仅当签名 Host 与实际传输地址不同时配置 `AGENT_REMOTE_TRANSPORT_OVERRIDES`；传输会保留原始 Host 和查询签名。临时文件在请求结束后清理，不要把完整签名 URL 写入日志或报告。

## 可复用知识库

知识库核心位于 `src/knowledge_base/`，目录固定为：

```text
data/knowledge_bases/<agent-namespace>/<knowledge-base-name>/
├── documents/
├── chroma/
└── manifest.json
```

namespace 和知识库名称必须是安全 slug。不同 namespace、知识库及 Chroma collection 完全隔离；旧 primary/secondary 配置和数据不兼容，也不迁移。

当前 worker 使用 namespace `langchain-knowledge-base-agent` 和默认知识库 `default`。本地管理示例：

```powershell
python -m src.knowledge_base documents-dir default
python -m src.knowledge_base ingest default
python -m src.knowledge_base retrieve default "检索问题"
python -m src.knowledge_base list
```

容器内可将 `python -m src.knowledge_base` 替换为 `docker compose exec langchain-knowledge-base python -m src.knowledge_base`。worker 内部还提供：

```text
GET  /v1/knowledge-bases
POST /v1/knowledge-bases/{name}/ingest
POST /v1/knowledge-bases/{name}/retrieval
```

这些管理接口不由首版网关公开。新智能体直接复用 `KnowledgeBaseManager(namespace)`，并使用自己的稳定 namespace。

当前知识库默认通过 GPU Stack调用 `deepseek-v4-flash` 问答，并使用
`qwen3-vl-embedding-8b`。嵌入模型或 Base URL变化时必须显式
`ingest --rebuild`，不得将旧向量与新向量混用。

### 八部门隔离知识库

模型 `department-knowledge-base-agent` 在同一
`POST /v1/chat/completions` 请求中接受与 `thinking` 同级的 `knowledge_id`。
可选值固定为：

```text
company-leadership
marketing
technical-support
project-delivery
operations-service
procurement-implementation
finance
general-management
```

网关原样转发扩展字段，worker 再做白名单校验。平台可创建八个模型配置，Base URL、
模型 ID 和 API key 相同，只固定不同 `knowledge_id`；部门用户不获得 API key，也不能
从对话文本切换部门。

附件可通过 `files` 数组、`file_url` / `image_url` content parts或消息中的 HTTP(S)
URL传入。Qwen3.5只做意图分类；仅当分类为 `save` 且存在附件时，worker才把原件归档
到本项目专属 MinIO并更新该部门 Chroma。专属 MinIO只在 Compose内部暴露
`department-kb-minio:9000`，不发布宿主机端口；八个部门分别使用独立 bucket。
详细协议、bucket、OCR和 dry-run说明见
`src/agents/department_knowledge_base/README.md`。

## 图片生成模型

`image-generation-agent` 接受文本、HTTP(S) `image_url`、Base64 data URL和带 MIME
的原始 Base64。无底图时文生图，有底图时编辑；没有新上传图时会读取最近助手图片。
最终响应使用多模态 content数组。AI 应用平台接入前必须完成
`docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`。

## 新增模型

1. 为智能体提供 `GET /health`、`GET /v1/models` 和 `POST /v1/chat/completions`。
2. 在 `config/agent_gateway.json` 登记稳定模型 ID、模块入口和 worker URL。
3. 在 `compose.yaml` 新增独立 worker 服务，内部监听 `8080`，不要发布宿主机端口。
4. 更新智能体登记表和平台文档，并补充网关聚合、流式代理和故障隔离测试。
