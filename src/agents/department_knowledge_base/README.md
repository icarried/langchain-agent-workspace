# Department Knowledge Base Agent

面向八个部门的隔离知识库智能体。生产统一使用：

```text
Base URL: http://<host>:8008/v1
Model: department-knowledge-base-agent
```

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
平台应在八个模型配置中固定不同 `knowledge_id`，不要让部门用户编辑该字段。

Qwen3.5 把请求分类为：

- `save`：明确要求保存、入库、归档或更新附件；
- `query`：依据当前部门知识库问答；
- `list`：列出当前部门文档；
- `help`：使用说明；
- `unknown`：删除、跨部门、权限变更或意图不清。

“有附件”本身不等于保存。只有 `save` 且实际存在附件时才写入；问答请求携带的附件
不会静默入库。删除不交给意图模型执行，后续应通过管理员审计接口实现。
同名新文件会替换当前可检索快照，避免新旧制度同时参与回答；MinIO 中的 SHA-256
内容寻址原件不会被覆盖，因此旧版仍可由管理员审计或恢复。

## 数据与对象存储隔离

每个部门同时拥有：

```text
Chroma/解析快照:
data/knowledge_bases/department-knowledge-base-agent/<knowledge_id>/

MinIO 原件 bucket:
department-kb-<knowledge_id>
```

`ai-app-platform` 的 MinIO 只作为上传入口。worker 下载附件后，先把原件写入本项目
专属 `department-kb-minio`，对象键为内容哈希路径，再保存本地解析快照并更新 Chroma。
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

TXT/Markdown、文本型 DOCX/PDF 优先本地解析。扫描 PDF按页渲染，图片和图片型 DOCX
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
