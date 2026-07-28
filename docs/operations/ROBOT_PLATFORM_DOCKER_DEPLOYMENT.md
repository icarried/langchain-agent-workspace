# 机器人管理平台服务器 Docker 部署

本文档说明如何把工作区统一智能体网关部署到机器人管理平台服务器。目标主机通过
WSL `Ubuntu` 中的 SSH 别名 `robotpl` 访问，运行目录固定为
`/opt/agent-workspace`。

## 部署边界

- 发布工作区 `linux/amd64` 镜像，运行 gateway 和八个隔离 worker；同时发布固定版本
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` 镜像。
- 只发布宿主机端口 `10085` 到容器网关 `8008`；worker 仅在 Compose 网络内监听
  `8080`。
- 服务器直接访问 `http://10.100.5.33:8003/v1`，不启用本机
  `local-proxy` profile，不设置 `GPU_STACK_CONTAINER_PROXY_URL`。
- 不迁移本机 `knowledge_base_data` 或 `department_kb_minio_data` 卷。首次启动会创建
  空卷，后续升级保留两者。
- 发布包不包含 `.env.local` 或其他真实密钥。

## 目录与发布物

```text
/opt/agent-workspace/
├── compose.yaml
├── .env
├── .env.local
├── current-release
└── releases/
    └── <release-id>/
        ├── compose.yaml
        ├── .env.example
        ├── agent-workspace-linux-amd64.tar.gz
        ├── department-kb-minio-linux-amd64.tar.gz
        └── SHA256SUMS
```

`.env` 只保存镜像标签和公开端口，供 Compose 插值；`.env.local` 是服务器运行密钥
文件，权限应为 `0600`。`current-release` 记录当前版本标签，但不包含密钥。

## 本机构建与打包

Docker 位于 WSL `Ubuntu`。当前 Windows 挂载路径含中文，构建时继续禁用
BuildKit：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/e/My_sorcode/--创建智能体工作空间-- && DOCKER_BUILDKIT=0 docker compose build gateway'
```

为镜像增加不可变发布标签，然后导出并生成校验：

```bash
docker tag agent-workspace:latest agent-workspace:<release-id>
docker save agent-workspace:<release-id> | gzip -1 > agent-workspace-linux-amd64.tar.gz
docker save quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z \
  | gzip -1 > department-kb-minio-linux-amd64.tar.gz
sha256sum agent-workspace-linux-amd64.tar.gz \
  department-kb-minio-linux-amd64.tar.gz compose.yaml .env.example > SHA256SUMS
```

上传优先使用断点续传：

```bash
rsync -av --partial --append-verify --info=progress2 \
  ./release/ robotpl:/opt/agent-workspace/releases/<release-id>/
```

## 服务器配置与启动

服务器 `.env` 设置：

```text
AGENT_WORKSPACE_IMAGE=agent-workspace:<release-id>
AGENT_GATEWAY_PORT=10085
```

服务器 `.env.local` 至少应设置：

```text
AGENT_GATEWAY_API_KEY=<独立生成的生产密钥>
GPU_STACK_BASE_URL=http://10.100.5.33:8003/v1
GPU_STACK_API_KEY=<GPU Stack 密钥>
GPU_STACK_CONTAINER_PROXY_URL=
DEPARTMENT_KB_MINIO_ACCESS_KEY=<项目独立随机账号>
DEPARTMENT_KB_MINIO_SECRET_KEY=<项目独立强密码>
DEPARTMENT_KB_OBJECT_STORE_ENABLED=true
```

知识库 chat/embedding key 可与 GPU Stack key 使用同一凭证，但仍通过
`KB_OPENAI_API_KEY` 和 `KB_EMBEDDING_API_KEY` 分别注入。不要复用
`GPU_STACK_API_KEY` 作为网关对外鉴权密钥。

校验、导入和启动：

```bash
cd /opt/agent-workspace/releases/<release-id>
sha256sum -c SHA256SUMS
gzip -dc agent-workspace-linux-amd64.tar.gz | docker load
gzip -dc department-kb-minio-linux-amd64.tar.gz | docker load

cd /opt/agent-workspace
docker compose config --quiet
docker compose up -d --no-build --pull never
```

不要在服务器启用 `--profile local-proxy`。不要执行 `docker compose down -v`，
否则会删除服务器知识库卷和部门原件 MinIO 卷。

## 验证

```bash
docker compose ps
curl -fsS http://127.0.0.1:10085/health
curl -fsS -H "Authorization: Bearer <AGENT_GATEWAY_API_KEY>" \
  http://127.0.0.1:10085/v1/models
docker compose exec image-generation \
  python -c "import urllib.request; print(urllib.request.urlopen('http://10.100.5.33:8003/v1/models').status)"
docker compose exec department-knowledge-base \
  python -c "import urllib.request; print(urllib.request.urlopen('http://department-kb-minio:9000/minio/health/live').status)"
```

最后一条未带 GPU Stack 密钥时预期返回 HTTP `401`；这表示容器网络已直达目标。
正式模型调用应通过带密钥的 agent 请求验证。

## 升级与回滚

升级前保留上一版 release 目录和镜像。切换版本时修改 `.env.local` 中
`AGENT_WORKSPACE_IMAGE`，同步对应 release 的 `compose.yaml` 到运行目录，再执行：

```bash
docker compose up -d --no-build --pull never
```

回滚时把同一变量和 Compose 文件恢复为上一版后重复启动命令。升级和回滚都不需要
停止或删除 `knowledge_base_data`、`department_kb_minio_data` 卷。

## 备份要求

`knowledge_base_data` 保存 Chroma与可重复解析的本地快照，
`department_kb_minio_data` 保存八部门长期原件；两者都必须纳入服务器备份。备份前
应暂停 `department-knowledge-base` worker，避免一次保存请求跨两个卷时取得不一致
快照。恢复后先验证 MinIO健康和八个 bucket，再对受影响知识库执行显式重建索引。
