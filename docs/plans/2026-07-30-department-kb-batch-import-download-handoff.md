# 部门知识库批量导入、智能检索、DOC 与来源下载 Handoff

## 目标与边界

关联任务：T-052。

- 所有保存请求进入卷内持久化导入任务，生产默认最多 100 份附件。
- 批次允许部分成功；全部有效文件只发布一次，失败不得破坏当前活动索引。
- 支持旧版 `.doc`，解析时临时转换，长期原件和下载保持原始字节与文件名。
- 提问由 DeepSeek改写/拆分为检索查询，多路召回后融合回答。
- 用户来源只显示去重文档名，不显示 `#chunk-*`。
- 下载仅随本次检索来源返回，不增加下载意图，也不解析上一轮回答。
- 不新增 PostgreSQL、Redis或消息队列。
- 不改变 AI应用平台上传、PG文件记录、MinIO或前端下载模型。平台仅扩展既有
  `delta.file` 安全验证器支持的文件类型。
- 服务器部署前必须由用户确认；不得执行 `docker compose down -v`。

## 已确认的旧实现缺陷

用户提供的 `C:\Users\Lenovo\Desktop\thinking.txt` 记录了一次 20 文件保存：

- 新附件接收和归档均为 20 份；
- 随后却从 `1/449` 到 `449/449` 重新解析活动目录全部文档；
- 最后重新生成 3070 个检索分块向量。

因此旧保存是“每批全量重建”，文档越多越慢，也会放大 SSE超时、OCR和 embedding
开销。本次必须同时修复，否则把附件上限提高到 100 只会进一步放大问题。

## 实现设计

### 1. 持久批量任务

任务目录位于知识库命名卷的 `.import_tasks/<knowledge_id>/<task_id>/`：

- 任务状态：`queued / receiving / processing / publishing / completed / partial /
  failed`。
- 文件状态：`pending / staged / parsed / archived / published / failed`。
- `task.json` 使用临时文件原子替换，只保存原名、SHA、大小、MIME、来源方式、阶段和
  结果，绝不保存预签名 URL。
- 暂存文件逐份落盘，任务终态后删除；终态 JSON默认保留 30 天。
- 全局默认两个执行线程，每个知识空间同时只发布一个任务。
- 流式请求先返回任务编号并订阅进度；断开不会取消后台线程。
- 非流式请求立即返回已受理和任务编号。
- `import_status` 可查询当前部门最近任务或指定 32 位任务编号。
- 启动恢复未完成任务：已暂存文件继续；未完成下载的文件标记需重新上传。

限制：

- 单批默认 100 份，可配置范围 1–500；
- 单文件 50 MiB；
- 单批 500 MiB；
- 单文档 100 页/图片；
- 单批累计 1000 个 OCR页/图片。

同一批次同名同 SHA视为幂等；同名不同内容按输入顺序保留第一份，后续项失败。有效
文件可以整体发布为 `partial`，无有效文件则 `failed`。

### 2. 增量原子索引

普通保存不再扫描和重新嵌入全部历史文档：

1. 复制当前活动版本的文档目录和不可变 Chroma目录到新版本暂存目录。
2. 应用本批有效文档更新，并用 SHA比较得到实际变化来源。
3. 只解析发生变化的文档；预检得到的 `DocumentRecord` 直接复用，避免重复 OCR。
4. 在新 Chroma副本中按 metadata `source` 删除这些文档的旧 chunk。
5. 只嵌入并追加这些文档的新 chunk。
6. 校验 `旧计数 - 删除数 + 新增数 == 新索引计数`。
7. 写版本 manifest，再原子替换根 manifest 的 `active_version`。

首次建库、显式 rebuild和 embedding签名变化仍执行全量重建。任一解析、嵌入、计数或
manifest发布失败都不切换活动版本。

### 3. DOC

- 共享转换器位于 `src/document_conversion.py`，批量简历包保留薄转发。
- Linux使用 LibreOffice Writer headless，转换超时默认 60 秒。
- `.doc` 只在解析阶段转换为 DOCX；活动快照、manifest、MinIO对象和下载载荷均保留
  原 `.doc` 名称、SHA和字节。

### 4. 智能提问

流程：

```text
query intent
  -> DeepSeek rewrite_queries
  -> batch vector retrieval
  -> chunk dedupe + RRF
  -> evidence-limited answer
  -> unique source documents
  -> delta.file for those sources
```

- 默认改写模型 `deepseek-v4-flash`，最多 5 个查询。
- 原问题始终参与检索；改写超时、非法 JSON或模型失败时降级为原问题。
- 多查询一次批量生成向量并查询同一活动 Chroma，单查询默认取 5 项。
- 使用 RRF融合，最终默认最多 20 个 chunk、10 个不同文档。
- 第一版不增加独立 reranker。
- 最终回答只接收原问题和融合证据；证据不足时拒答，不用外部常识补全。
- chunk ID、chunk index和分数继续保留在内部 citation，用户只看到文档名。
- 同一文档命中多个 chunk 时来源只列一次。

参考 DSL：

`E:\浏览器下载\安全法律法规知识智能体 v0.2 (1).yml`

### 5. 来源下载

- 只对 `query` 的结构化 `source_documents` 读取当前活动版本原件。
- 文件必须位于活动文档目录内，重新计算 SHA并与 manifest/citation目录记录核对。
- 按来源顺序发送，最多 10 份、总计最多 50 MiB。
- 流式响应在回答和“来源”之后连续发送既有 `delta.file`。
- 非流式响应使用同一 assistant message 的 `files` 数组。
- 载荷沿用公文格式化智能体：

```json
{
  "status": "completed",
  "filename": "采购管理办法.doc",
  "file_type": "doc",
  "mime_type": "application/msword",
  "encoding": "base64",
  "content_base64": "...",
  "sha256": "...",
  "size": 1234
}
```

保存结果、文档列表、任务状态和帮助响应不发送文件。不存在独立 `download` 意图。

### 6. AI 应用平台最小改动

平台已经完整消费 `delta.file`，将文件写入平台 MinIO和 `file_mapping`，前端也已经
显示下载控件。无需新增 `file_reference`、`file_id` 转发、应用归属字段、数据库迁移
或前端代码。

唯一必要修改是扩展模型生成文件验证入口：

- 文档：PDF、DOC、DOCX、TXT、MD、Markdown；
- 图片：PNG、JPEG、WEBP、BMP、TIFF；
- DOC使用 OLE结构检查，拒绝宏、加密、混淆、对象池和主动嵌入；
- DOCX继续拒绝宏、ActiveX、外部关系和嵌入对象；
- PDF继续拒绝 JavaScript、Launch、OpenAction、加密和嵌入文件；
- 文本必须是 UTF-8且不含二进制控制字符；
- 图片由 Pillow解码、校验真实格式、尺寸和像素上限；
- SVG和未知/可执行格式继续拒绝。

平台上传链路、数据库、对象存储服务和前端保持不变。

### 7. 用户帮助

```text
支持：基于本部门知识库问答；上传附件并明确说“保存/入库/归档”；
查看本部门已保存文档和批量导入进度。知识库回答引用的来源文档会在“来源”下提供
下载（一次最多 10 份）。
不支持通过对话删除资料。
```

用户展示中不再出现“切换部门或访问其他部门知识库”；服务端固定 `knowledge_id`、
部门隔离和越权拒绝逻辑保持不变。

## 当前实现状态

已完成主体代码：

- 持久任务协调器、进度查询、部分成功和恢复；
- 默认 100、单文件/批次/OCR限制；
- 共享 DOC转换器和知识库 `.doc` loader；
- 查询改写、批量检索、RRF和证据回答；
- 去重文档来源及无 chunk标签输出；
- 来源原件 `delta.file`；
- 增量 Chroma复制、按来源删除/追加和原子 manifest；
- 健康接口的队列长度、活动任务数和查询改写状态；
- 平台多类型生成文件安全验证。

已完成验证：

- Agent聚焦测试 41 项通过；
- Agent聚焦 Ruff通过；
- 平台生成文件、LLM消费聚焦测试 46 项通过；
- 平台新增文件静态检查通过。

仍需：

- 两仓库全量测试和静态检查；
- Compose配置及本地镜像构建；
- 本地 100 文件、断开 SSE、任务状态、DOC和来源下载端到端；
- 更新最终运维记录；
- 准备不可变镜像和 Git bundle；
- 在服务器部署前向用户确认。

## 验收重点

- 100 份受理，101 份在下载前拒绝。
- 20 份新文件进入已有 449 文档知识库时，只解析/嵌入实际变化的 20 份，不再出现
  `1/469` 一类全量进度。
- 一批正常 TXT/PDF/DOC与损坏文件得到 `partial`，只发布有效文件。
- 嵌入失败时根 manifest和旧 Chroma保持不变。
- SSE断开后任务继续；重启后已暂存文件恢复；任务 JSON无 URL。
- DOC可检索，下载字节和入库 SHA一致。
- 复合问题产生多查询召回，改写失败可降级。
- 来源没有 `#chunk-*`，同文档只出现一次。
- 多份 `delta.file` 均被平台持久化、展示并可下载。
- 平台拒绝 DOC宏/加密、损坏格式、MIME/扩展名不一致、Base64/SHA/大小不一致。

## 部署顺序与约束

1. 先部署 AI应用平台的纯类型验证扩展，使其能消费知识库返回的新格式。
2. 再部署 agent-workspace不可变镜像。
3. 保留平台 PG/MinIO、`knowledge_base_data` 和 `department_kb_minio_data`。
4. 禁止 `down -v`。
5. 生产只做健康、模型发现、100附件 dry-run、任务状态和下载协议检查，不向正式部门
   知识库写入测试资料。
6. 回滚先回滚 agent-workspace，再回滚平台。
