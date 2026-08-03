# 本机部署与开发环境搭建 Handoff（含新机器从头部署）

> 目的：让两类人都不依赖原执行人即可工作——
> 1. **新机器用户**：拉取 git 后按第 2 节从头部署本机开发环境与本地 Compose；
> 2. **本机接手者**：按第 3 节环境快照和第 4 节速查恢复、排查。
>
> 本文只记录可验证事实、命令归属和文档索引，不存放任何真实密钥。

## 1. 部署模型（先理解再动手）

- 代码只有一份：Windows 侧目录（conda 开发/测试）与 WSL 挂载路径（Docker 构建运行）
  指向同一份文件。
- 运行全部走 Docker Compose：项目名 `agent-workspace`，文件为根目录 `compose.yaml`。
  仅 gateway 对外发布 `8008`；worker 只在 Compose 内部监听 `8080`。
- 密钥只在 `.env.local`（git 忽略），Compose 通过 `env_file: .env.local` 注入。
- 代理是**部署时决策项**：原机 GPU Stack / ComfyUI 需要 `127.0.0.1:7897` 代理；
  新机器若内网直连则不需要。先确认再配置（见 2.5）。

### git 拉取后仓库里有什么 / 没有什么

克隆后**有**：`.env.example`、`compose.yaml`、`environment.yml`、
`requirements-linux.txt`、`Dockerfile`、全部源码与测试、`scripts/check_local_env.ps1`。

克隆后**没有**（gitignore 排除，需自行准备）：

```text
.env                # 本机 Compose 覆盖（local-proxy profile），未提交
.env.local          # 真实密钥，未提交
secrets/            # 密钥归档，未提交
local-deployment/   # 服务器发布物料，未提交
data/knowledge_bases/  # 知识库数据卷挂载点，未提交
临时文件/            # 运行输出，未提交
```

## 2. 新机器从头部署（主流程）

按顺序执行；每一步都有验证命令，FAIL 后不要跳过。

### 2.0 前置条件

| 依赖 | 要求 | 原机参考 |
| --- | --- | --- |
| Windows | Windows 10/11 64 位，启用 WSL2 | Windows 10 Home |
| WSL | 一个 Linux 发行版（推荐 Ubuntu 24.04），systemd 开启 | `Ubuntu` 24.04.3 LTS |
| Docker | Docker Engine 在 WSL 内（或 Docker Desktop + WSL 集成） | Docker 28.5.1 |
| Conda | Miniforge 或等效发行 | Miniforge，`langchain` 环境 Python 3.11 |
| 网络 | 能拉取仓库、pip/apt 源（或本地代理 `127.0.0.1:7897`） | 见 2.5 |

安装示例（管理员 PowerShell）：

```powershell
wsl --install -d Ubuntu
# WSL 内安装 Docker Engine 后确认：
wsl -d Ubuntu -- bash -lc 'systemctl is-system-running; docker version --format "{{.Server.Version}}"'
```

### 2.1 拉取代码（建议纯 ASCII 路径）

```powershell
git clone <仓库地址> D:\agent-workspace
cd D:\agent-workspace
git log -1 --oneline
```

> 原机路径 `E:\My_sorcode\--创建智能体工作空间--` 含中文，触发 Docker BuildKit 的
> 会话头 ASCII 错误，必须 `DOCKER_BUILDKIT=0`。新机器 clone 到纯 ASCII 路径后，
> 可直接用默认 BuildKit（见 2.6 说明）。

### 2.2 环境自检

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_env.ps1
# 可选：附带网关 8008 检查（读取 .env.local 的 AGENT_GATEWAY_API_KEY，只显示模型数量）
powershell -ExecutionPolicy Bypass -File .\scripts\check_local_env.ps1 -IncludeGatewayCheck
```

脚本只读，输出 PASS / WARN / FAIL 报告，覆盖：git 仓库、conda `langchain` 环境、
WSL 发行版与 Docker 归属、Windows→WSL 路径映射、`.env.local` 关键变量名、
`compose.yaml` 校验，以及可选的网关检查。消息为英文；脚本不会修改文件、不会启动
服务、不打印密钥值。修复所有 FAIL 后再继续。

> **Codex 沙箱可见性**：在 Codex 工具内直接运行脚本时，WSL/Docker 探测可能显示
> FAIL（受限用户看不到发行版），但网关检查仍可工作。这是沙箱限制，不是脚本缺陷；
> 请在普通 PowerShell 终端运行脚本获取真实结果。

### 2.3 确认 WSL 与 Docker 归属

```powershell
wsl.exe -l -q                 # 列出发行版名
wsl.exe -d <distro> -- bash -lc 'docker version --format "{{.Server.Version}}"'
wsl.exe -d <distro> -- wslpath -a 'D:\agent-workspace'   # 期望如 /mnt/d/agent-workspace
```

- 本文所有 `<distro>` 换成你的实际发行版名（原机为 `Ubuntu`）。
- 若 Docker 属于 Docker Desktop（Windows 侧）而不是 WSL，后续 `docker compose` 可在
  Windows PowerShell 执行；但 2.5 的 `local-proxy` relay 按 WSL Docker 设计，Docker
  Desktop 场景需另行调整或选直连方案 B。

### 2.4 创建 conda 开发环境

```powershell
conda env create -f environment.yml          # 首次
conda env update -f environment.yml --prune  # 已有环境时更新
conda activate langchain
python -c "import langchain, langgraph; print('ok')"
```

说明：
- `environment.yml` 固定 Python 3.11，并含 langchain 全家桶、chromadb、minio、mcp、
  fastmcp、uvicorn、pytest、ruff 等。
- `pywin32` 仅 Windows 安装（`platform_system == "Windows"`）；Linux 侧依赖只用于
  Docker 镜像，见 `requirements-linux.txt`。
- conda 环境真实位置可用 `conda env list` 查到；找不到 `conda` 命令时，用 Miniforge
  安装目录里的 `conda.bat` / `conda.exe`。

### 2.5 准备环境变量

**第一步：密钥模板**

```powershell
Copy-Item .env.example .env.local
```

在 `.env.local` 中填写（值不提交、不回显）：

| 变量 | 用途 | 是否必填 |
| --- | --- | --- |
| `GPU_STACK_API_KEY` + `GPU_STACK_BASE_URL` | 默认模型/嵌入/OCR 凭证源 | 是 |
| `AGENT_GATEWAY_API_KEY` | 网关 Bearer 鉴权；留空则网关不鉴权 | 建议 |
| `AGENT_MCP_TOKENS_JSON` | MCP 工具权限 map（本地可先配单个 token） | 用 MCP 时 |
| `DEPARTMENT_KB_MINIO_ACCESS_KEY` / `DEPARTMENT_KB_MINIO_SECRET_KEY` | 部门知识库专属 MinIO；Compose 启动强校验非空 | 是 |
| `KB_*`、`DEPARTMENT_KB_*`、`COMFYUI_*`、`IMAGE_*` | 各智能体覆盖变量 | 可选 |

**第二步：代理决策（两选一）**

- **方案 A（本机需要代理，与原机一致）**：创建未提交的根目录 `.env`：

  ```env
  COMPOSE_PROFILES=local-proxy
  GPU_STACK_CONTAINER_PROXY_URL=http://host.docker.internal:17897
  ```

  同时验证 WSL 内 `127.0.0.1:7897` 可用：

  ```powershell
  wsl.exe -d <distro> -- bash -lc 'curl -fsS --max-time 5 --proxy http://127.0.0.1:7897 https://pypi.org/simple/pip/ >/dev/null && echo PROXY_OK'
  ```

- **方案 B（新机器内网直连）**：不创建 `.env`，`GPU_STACK_CONTAINER_PROXY_URL` 保持
  为空，worker 直连 `GPU_STACK_BASE_URL`。**服务器部署永远用方案 B。**

### 2.6 构建与启动 Compose

```powershell
# 先校验 Compose 配置
wsl.exe -d <distro> -- bash -lc 'cd /mnt/d/agent-workspace && docker compose config --quiet && echo COMPOSE_OK'

# 构建 + 启动（首次构建会拉 python:3.11-slim 并 apt 安装 libreoffice-writer，需要网络）
wsl.exe -d <distro> -- bash -lc 'cd /mnt/d/agent-workspace && docker compose build gateway && docker compose up -d'
```

- 只有碰到 BuildKit 的 ASCII 报错（中文路径、旧环境）才退回
  `DOCKER_BUILDKIT=0 docker compose build gateway`。
- 首次拉基础镜像慢时，可给 Docker 配置镜像加速器；不要因此改业务镜像 tag 语义。
- 日常代码更新：`docker compose build gateway && docker compose up -d --force-recreate gateway`
  （gateway 与 worker 共用镜像 `agent-workspace:latest`）。
- 生产/服务器发布流程见 `docs/operations/ROBOT_PLATFORM_DOCKER_DEPLOYMENT.md`，
  本机步骤不适用服务器。

### 2.7 验收清单

```powershell
# 1) 容器全部 healthy，仅 gateway 发布 8008
wsl.exe -d <distro> -- bash -lc 'cd /mnt/d/agent-workspace && docker compose ps'

# 2) 网关模型列表（带 key；当前应为 11 个健康模型）
$key = ((Get-Content .env.local | Where-Object { $_ -match '^AGENT_GATEWAY_API_KEY=' }) -split '=',2)[1]
Invoke-RestMethod -Uri http://127.0.0.1:8008/v1/models -Headers @{ Authorization = "Bearer $key" } |
  ForEach-Object { $_.data.id }

# 3) 网关健康
Invoke-RestMethod http://127.0.0.1:8008/health

# 4) MCP 入口（需 MCP 客户端/SDK，非普通 REST）：http://127.0.0.1:8008/mcp

# 5) 故障隔离脚本（会临时停/恢复 contract-review worker，只读验收用）
wsl.exe -d <distro> -- bash -lc 'cd /mnt/d/agent-workspace && python3 scripts/verify_agent_gateway_isolation.py'
```

期望的 11 个模型 ID：

```text
batch-resume-review-agent        tender-format-review-agent
smart-resume-screening-agent     contract-review-agent
official-document-review-agent   official-document-formatting-agent
langchain-knowledge-base-agent   department-knowledge-base-agent
image-generation-agent           comfyui-video-generation-agent
comfyui-image-to-video-agent
```

单模型本地开发（不启 Compose）：

```powershell
python -m src.agent_gateway dev --port 8008 --models <model-id>
```

### 2.8 从头部署常见失败点

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 自检脚本显示 WSL/Docker FAIL，但本机明明可用 | Codex 沙箱受限用户看不到 WSL 发行版 | 在普通 PowerShell 终端运行脚本；以真实结果为准 |
| 构建报 ASCII / BuildKit 错误 | 路径含中文或旧环境 | `DOCKER_BUILDKIT=0`，或 clone 到 ASCII 路径 |
| `docker: command not found` | Docker 在 WSL 内未装/未启动 | `wsl -d <distro> -- docker version`；检查 systemd |
| `conda` 找不到或权限失败 | 未装 Miniforge / 沙箱 Temp 限制 | 用 `D:\ProgramData\miniforge3\...\conda.bat` 或直接调用 `conda env list` 得到的 python.exe |
| `/v1/models` 返回空 | 网关已启用 `AGENT_GATEWAY_API_KEY` | 请求带 Bearer，或用 `-IncludeGatewayCheck` 复验 |
| 容器内 GPU Stack 不通 | 代理决策与机器不符 | 对照 2.5：本机需代理用 A，直连用 B |
| `department-kb-minio` 起不来 | `DEPARTMENT_KB_MINIO_*` 为空 | 在 `.env.local` 填两个变量后重启 Compose |
| 8008 端口占用 | 本机已有服务 | 停旧服务，或 `AGENT_GATEWAY_PORT=<其他>` 覆盖 |
| worker 健康但模型缺失 | 配置/上游不可达 | 查 `docker compose logs <worker>`；`/health` 看脱敏状态 |

## 3. 原机（2026-08-03）实测快照

> 本节是**参考实例**，不是新机器硬性要求；换机后以第 2 节流程和自检结果为准。

### 3.1 Windows 侧

| 项目 | 事实 | 观察范围 |
| --- | --- | --- |
| 系统 | Windows 10 Home China（构建 2009） | 系统账本 |
| 默认 shell | PowerShell；自动化偏好 PowerShell 7.5.5 | 系统账本 |
| Conda | Miniforge，入口 `D:\ProgramData\miniforge3\Library\bin\conda.bat`；`langchain` 位于 `C:\Users\Lenovo\.conda\envs\langchain` | 实测 |
| 项目路径 | `E:\My_sorcode\--创建智能体工作空间--`（含中文） | 实测 |
| WSL 可见性 | Codex 沙箱 `wsl.exe -l -v` 可能看不到发行版，但 `wsl.exe -d Ubuntu` 可直接调用（沙箱可见性限制，不是机器事实） | 系统账本 |

`langchain` 环境实测：Python 3.11.15，langchain 1.2.18，langgraph 可用。

### 3.2 WSL 侧

| 项目 | 事实 |
| --- | --- |
| 发行版 | `Ubuntu`，Ubuntu 24.04.3 LTS（Noble Numbat），x86_64 |
| 内核 | 6.6.87.2-microsoft-standard-WSL2 |
| 默认用户 / shell | `enovo` / bash；`/etc/wsl.conf` 中 `systemd=true` |
| WSL 路径 | `/mnt/e/My_sorcode/--创建智能体工作空间--` |
| 网络 | eth0 持局域网地址 `10.71.2.94/23`；DNS `10.255.255.254`；默认路由经 `198.18.0.2` 与 `10.71.3.1` |
| GPU | NVIDIA GeForce RTX 5070 Laptop，驱动 591.86，8151 MiB |
| 独立 GPU Docling 环境 | `/home/enovo/.local/share/docling-gpu/venv`（与项目环境无关） |

### 3.3 Docker / Compose 现状

- Docker 由 WSL `Ubuntu` 管理：client/server 均为 28.5.1，context `default`
  （`unix:///var/run/docker.sock`）。Windows PATH 通常没有 `docker.exe`。
- 实测 15 个容器全部运行且 worker healthy；仅 gateway 发布 `0.0.0.0:8008->8008`：

  ```text
  gateway, mcp-gateway, batch-resume-review, tender-format-review,
  smart-resume-screening, contract-review, official-document-review,
  official-document-formatting, langchain-knowledge-base,
  department-knowledge-base, image-generation, comfyui-video-generation,
  comfyui-image-to-video, department-kb-minio, gpu-stack-proxy-relay
  ```

- 镜像 `agent-workspace:latest`（`AGENT_WORKSPACE_IMAGE` 可覆盖）；MinIO
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`。
- 网关鉴权实测：不带 `AGENT_GATEWAY_API_KEY` 返回空模型列表；带 Bearer 返回 11 个模型。
- 命名卷：`knowledge_base_data`（Chroma/快照/manifest）、
  `department_kb_minio_data`（部门原件）。**任何例行操作不得 `docker compose down -v`。**

### 3.4 网络与代理

- WSL 用户 `enovo` 经 `~/.profile` 加载 `~/.config/codex-proxy.env`：
  `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY=http://127.0.0.1:7897`，
  `NO_PROXY=localhost,127.0.0.1,::1`。
- GPU Stack（`10.100.5.33:8003/v1`）与 ComfyUI（`10.180.26.16:8188`）走该代理；
  本机不要把 `10.100.5.33`、`10.180.0.0/16` 加进 `NO_PROXY`。
- 容器经 `local-proxy` profile 的 `gpu-stack-proxy-relay`（host network，
  `172.17.0.1:17897`）把 `host.docker.internal:17897` 转发到 WSL `127.0.0.1:7897`。
- WSL Docker 还有其他平台容器（FastGPT `3000`、`fastgpt-minio` `9002/9003`、
  独立 MinIO `9000/9001`），属于外部平台，不在本项目 Compose 内。

## 4. 常用命令速查（按执行环境）

> `<distro>` 替换为实际发行版名；`<wsl-root>` 用 `wslpath` 求得。

| 任务 | 执行环境 | 命令 |
| --- | --- | --- |
| 环境自检 | Windows PowerShell | `powershell -ExecutionPolicy Bypass -File .\scripts\check_local_env.ps1` |
| 启动统一网关（本机） | Windows PowerShell | `python -m src.agent_gateway dev --port 8008` |
| 构建 + 启动 Compose | WSL | `docker compose build gateway && docker compose up -d` |
| 查看容器 | WSL | `docker compose ps` |
| 网关模型列表 | Windows PowerShell | 带 key 的 `Invoke-RestMethod http://127.0.0.1:8008/v1/models` |
| 全量测试 | Windows PowerShell | `python -m pytest tests -q` |
| 静态检查 | Windows PowerShell | `ruff check .` |
| 故障隔离验收 | WSL | `python3 scripts/verify_agent_gateway_isolation.py` |
| 知识库 CLI | Windows PowerShell | `python -m src.knowledge_base list / ingest default / retrieve default "问题"` |
| 视频链路验收 | Windows PowerShell | `python scripts/test_ai_app_video_agent.py --base-url http://127.0.0.1:8008/v1` |

单智能体 REST/MCP 调试端口（8001/8002/8003/8005/8006/8007/18004 等）仅用于开发，
生产一律走 `8008`。

## 5. 迁移检查清单（换机 / 换路径后）

- [ ] `git clone` 到纯 ASCII 路径；`git log -1` 确认提交。
- [ ] `scripts/check_local_env.ps1` 无 FAIL（WARN 需读懂原因）。
- [ ] WSL 发行版、Docker 归属已确认；`wslpath` 映射正确。
- [ ] conda `langchain` 环境可导入 langchain/langgraph。
- [ ] `.env.local` 已从模板重建并填齐必填变量；`.env` 按代理决策配置（A/B）。
- [ ] `docker compose config --quiet` 通过；Compose 项目名 `agent-workspace`。
- [ ] `docker compose ps` 全部 healthy；仅 gateway 发布 8008。
- [ ] 网关带鉴权返回预期 11 个模型；`/health` 正常；`/mcp` 可握手。
- [ ] 命名卷存在且未误删；知识库数据按需导入。
- [ ] GPU Stack / ComfyUI 连通性按代理决策实测通过。

## 6. 上游文档索引

| 内容 | 路径 |
| --- | --- |
| Agent 入门规则 | `AGENTS.md` |
| 项目快速入口 | `README.md` |
| 运行调试手册（各智能体命令） | `docs/development/RUN_AND_DEBUG.md` |
| 环境自检脚本（只读） | `scripts/check_local_env.ps1` |
| 统一网关 / MCP 部署 | `docs/development/AGENT_GATEWAY.md` |
| conda 环境说明 | `docs/development/CONDA_LANGCHAIN_ENV.md` |
| 密钥变量清单 | `docs/operations/SECRETS.md` |
| 智能体登记表 | `docs/workspace/AGENT_REGISTRY.md` |
| 决策记录 / 问题日志 | `docs/workspace/DECISIONS.md` / `docs/operations/PROBLEM_LOG.md` |
| 服务器部署与回滚 | `local-deployment/本项目部署操作文档/`（未随 git 分发） |
| 环境账本 | `.codex/env/PROJECT_ENVIRONMENT.md`（未随 git 分发） |

> `local-deployment/` 与 `.codex/env/` 被 gitignore 排除，不会随克隆分发；服务器发布
> 文档需要时从原机拷贝或按 `docs/operations/ROBOT_PLATFORM_DOCKER_DEPLOYMENT.md`
> 重建。
