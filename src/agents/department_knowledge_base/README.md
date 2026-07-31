# Department Knowledge Base Agent

面向八个部门及“公司规定”的隔离知识库智能体。生产统一使用：

```text
Base URL: http://<host>:8008/v1
Model: department-knowledge-base-agent
```

统一 MCP入口为 `http://<host>:8008/mcp`，使用 Streamable HTTP和 Bearer token。
每个 token必须在 `DEPARTMENT_KB_MCP_TOKENS_JSON` 中固定绑定一个 `knowledge_id`；
三个只读工具的参数中均没有 `knowledge_id`，MCP客户端不能在调用时切换部门：

```text
department_kb_list_spaces
department_kb_query(question, top_k?)
department_kb_get_import_status(task_id?)
```

首期 MCP不提供保存、删除、重建或任意原件下载工具。

## 知识空间

| knowledge_id | 部门 |
| --- | --- |
| `company-leadership` | 公司领导层 |
| `marketing` | 市场营销部 |
| `technical-support` | 技术支撑部 |
| `project-delivery` | 项目交付部 |
| `operations-service` | 运维服务部 |
| `procurement-implementation` | 采购实施部 |
| `finance` | 经营财务部 |
| `general-management` | 综合管理部 |
| `company-regulations` | 公司规定 |

`knowledge_id` 是 Chat Completions 请求体中与 `thinking` 同级的扩展字段。网关会原样
转发未知 OpenAI 扩展字段。服务端只接受上表固定值，不从用户消息推导、覆盖或切换
部门；缺少或未知值的业务请求直接返回 400。

## 调用示例

问答：

```json
{
  "model": "department-knowledge-base-agent",
  "knowledge_id": "technical-support",
  "messages": [
    {"role": "user", "content": "故障升级流程是什么？"}
  ],
  "stream": true,
  "thinking": true
}
```

保存附件：

```json
{
  "model": "department-knowledge-base-agent",
  "knowledge_id": "technical-support",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "请把这份手册保存到知识库"},
        {
          "type": "file_url",
          "file_url": {
            "url": "https://upload-minio.example/uuid.pdf?X-Amz-Signature=...",
            "filename": "技术支撑手册.pdf"
          }
        }
      ]
    }
  ],
  "stream": true
}
```

结构化 `file_url.filename` 是保存业务原名的首选入口。worker 下载临时 URL，但以
经过 basename、Unicode NFC、控制字符和长度处理后的原名保存快照与原件；不会持久化
预签名 URL 或查询签名。也继续兼容 `image_url.url`、消息文本 HTTP(S) URL，以及
顶层字符串或 `{url, filename}` 对象形式的 `files`。重复 URL 同时从旧、新入口出现时
只保留一次，并优先采用带原名的引用。`files`、`knowledge_id` 都是本 worker 的
OpenAI-compatible 扩展字段。
平台应在九个模型配置中固定不同 `knowledge_id`，不要让用户编辑该字段。

Qwen3.5 把请求分类为：

- `save`：明确要求保存、入库、归档或更新附件；
- `query`：依据当前部门知识库问答；
- `list`：列出当前部门文档；
- `import_status`：查询当前部门最近或指定编号的导入任务；
- `help`：使用说明；
- `unknown`：删除、跨部门、权限变更或意图不清。

“有附件”本身不等于保存。只有 `save` 且实际存在附件时才写入；问答请求携带的附件
不会静默入库。删除不交给意图模型执行，后续应通过管理员审计接口实现。
同名新文件会替换当前可检索快照，避免新旧制度同时参与回答；MinIO 中的 SHA-256
内容寻址原件不会被覆盖，因此旧版仍可由管理员审计或恢复。

每次保存都会创建持久化导入任务，默认最多 100 份、单文件 50 MiB、单批 500 MiB。
流式保存会立即报告任务编号，随后逐文件报告暂存、解析、OCR、归档和原子发布；
连接断开不会取消后台任务。非流式请求立即返回任务编号。用户可说“查看导入进度”
或“查看任务 <任务编号>”。任务状态保留 30 天，但不保存预签名 URL。

新文档发布会复制当前不可变 Chroma 快照，只删除并重建本批发生变化的文档向量；
既有未变化文档不会再次解析或嵌入。只有首次建库、显式 rebuild 或 embedding 配置
变化时才执行全量重建。长步骤默认每 10 秒发送一次心跳，可用
`DEPARTMENT_KB_STREAM_HEARTBEAT_SECONDS` 调整。
这些内容是执行状态，不是模型隐藏思维链；`thinking=true` 时进入
`delta.reasoning_content`，否则进入普通 `delta.content`。

提问会先由 DeepSeek 将原问题改写/拆分为最多 5 个独立查询，再对当前活动快照执行
多查询召回和 RRF 融合；改写失败会自动回退到原问题，不影响问答。回答正文只使用
实际检索证据，来源按文档名去重，不向用户显示 `#chunk-*`。每个本次命中的当前来源
原件通过既有 `delta.file` 返回，最多 10 份、合计 50 MiB；AI 应用平台沿用现有
生成文件持久化和附件下载控件，不需要第二轮“下载”请求。

## 数据与对象存储隔离

每个部门同时拥有：

```text
Chroma/解析快照:
data/knowledge_bases/department-knowledge-base-agent/<knowledge_id>/

MinIO 原件 bucket:
department-kb-<knowledge_id>
```

`ai-app-platform` 的 MinIO 只作为上传入口。worker 下载附件后，先把原件写入本项目
专属 `department-kb-minio`，对象键为内容哈希路径，再在独立版本目录构建文档快照、
Chroma 和 manifest。新索引数量校验通过后，才原子替换根 manifest 中的
`active_version` 指针；构建失败不会修改当前可检索快照。默认保留当前版和上一版索引，
可用 `KB_VERSION_RETENTION` 调整。失败请求可能已经归档 MinIO 原件，但不得称为
“已完成索引”。

版本化布局：

```text
<knowledge_id>/
├── manifest.json                 # 当前 active_version，原子替换
├── documents/                    # 通用 CLI 的待入库工作目录/旧布局兼容
└── versions/<version-id>/
    ├── documents/
    ├── chroma/
    └── manifest.json
```

专属 MinIO 的 `9000/9001` 只在 Compose 网络中 `expose`，没有宿主机 `ports`，不会与
现有 `9000/9002` 冲突。不要给部门用户 MinIO 凭证或网关 API key。

生产必须在 `.env.local` 设置：

```env
DEPARTMENT_KB_MINIO_ACCESS_KEY=<独立随机用户名>
DEPARTMENT_KB_MINIO_SECRET_KEY=<独立强密码>
DEPARTMENT_KB_OBJECT_STORE_ENABLED=true
```

知识库卷和 `department_kb_minio_data` 都必须纳入服务器备份。禁止使用
`docker compose down -v`。MinIO 原件是长期档案副本，本地文档快照用于可重复解析和
重建向量索引；两者不能只备份其一。

## OCR

TXT/Markdown、文本型 DOCX/PDF 优先本地解析。旧版 `.doc` 在解析阶段通过
LibreOffice headless 临时转换为 DOCX，但活动快照、MinIO 和下载都保留原始 `.doc`
字节与文件名。扫描 PDF按页渲染，图片和图片型 DOCX
调用 GPU Stack `paddleocr-vl-1.6`。OCR 实现位于共享的 `src/document_ocr/` provider
接口，后续可替换为官方 PaddleOCR-VL完整 Serving流水线。

PaddleOCR官方说明单独调用 VLM组件不等同于完整的“布局分析 + VLM识别”流水线。
当前 GPU Stack端点用于逐页结构化 Markdown提取；复杂版面需要更高一致性时，应新增
官方完整 Serving provider。官方说明：
<https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html>

## 调试

```powershell
python -m src.agent_gateway dev --port 8008 --models department-knowledge-base-agent
python -m pytest tests\agents\test_department_knowledge_base_llm.py tests\test_document_ocr.py -q
```

由于生产对象存储地址使用 Compose DNS `department-kb-minio:9000`，Windows本地
supervisor适合 readiness、问答和 `dry_run` 调试；真实保存链路使用根 Compose验证。
若只调试本地文件解析，可在当前进程临时关闭对象存储，但不要把生产配置改为关闭。

无网络、无写入检查可在请求中传 `"dry_run": true`。它会验证
`knowledge_id`、附件解析和路由形态，但不会调用 Qwen/OCR、下载文件或写入存储。
