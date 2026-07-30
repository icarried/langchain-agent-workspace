# official-document-formatting

确定性公文格式化智能体。第一期只执行 DOCX 格式化规则，不调用大模型，不做内容润色、
删除或改写。规范依据为 `临时文件/公文格式化配置/公文格式规范.docx` 的正文要求。

## 能力

- 一次接收一份 DOCX，支持本地路径、HTTP(S) URL、平台 `附件：` 和
  OpenAI content parts 的 `file_url.url`。
- 显式设置 A4、上下左右 `3.7/3.5/2.8/2.6 cm` 页边距、`2.5 cm` 页脚、
  `560 twips` 页面网格和奇偶页动态 `－{PAGE}－` 页码。
- 确定性识别主标题、文号、签发人、主送机关、四级标题、正文、附件说明、正式附件、
  落款、日期、附注和版记，不调用 LLM。
- 正文及“一、”“（一）”“1.”“（1）”层级段落均以 OOXML 属性首行缩进 2 个中文
  字符；主送机关顶格，不向文字插入空格。
- `附件：` 独立成段并首行缩进 2 字，附件清单从下一段开始整体左缩进 2 字，项目换行
  与序号对齐。输入把首项写在 `附件：` 后时自动拆段，并清理清单项目的行首布局空白；
  附件名称保持不变。正式附件另面开始，标题按第三行位置设置。
- 落款和日期右空 4 字；版记使用四号仿宋、左右各空 1 字、上下边线和同页属性。
- 表格采用三线表：1.5 pt 顶线和底线、0.75 pt 表头下线，不写入左右线、竖线或内横线；
  首行设置为跨页重复表头，每条数据行设置为不跨页拆分。名称、规格、数量和金额等列按
  表头语义确定对齐方式。
- 格式化前后校验正文段落与表格单元格内容，任何变化都会拒绝输出。
- 支持 CLI、dry-run、OpenAI-compatible 非流式和 SSE。
- 正式结果通过非流式 `message.file` 或流式 `delta.file` 返回 Base64 DOCX、文件名、
  MIME、字节数和 SHA-256；智能体不连接 AI 平台 MinIO。

## CLI

```powershell
python -m src.agents.official_document_formatting format path\to\公文.docx --dry-run
python -m src.agents.official_document_formatting format path\to\公文.docx
python -m src.agents.official_document_formatting format path\to\公文.docx -o path\to\输出.docx
```

不指定 `--output` 时，CLI 输出为 `<原文件名>-公文格式化.docx`，且不会覆盖原文件。

## 统一平台入口

```text
Base URL: http://<可达网关地址>:8008/v1
Model: official-document-formatting-agent
Stream: 开启
```

推荐提示词：

```text
公文文件：
{{file_url}}

输出要求：请按公司标准格式化公文。
```

平台自动生成的 `附件：` 列表也可以直接使用。生产启用网关鉴权时发送
`Authorization: Bearer <AGENT_GATEWAY_API_KEY>`。

## 文件输出协议

最终流式 chunk 的核心字段：

```json
{
  "choices": [{
    "delta": {
      "file": {
        "status": "completed",
        "filename": "原文件名-公文格式化.docx",
        "file_type": "docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "encoding": "base64",
        "content_base64": "<base64>",
        "sha256": "<sha256>",
        "size": 12345
      }
    }
  }]
}
```

AI 平台负责解码、DOCX 安全校验、MinIO 持久化、`file_mapping` 和用户下载。

## 合规结果边界

报告把规则分为三类：

- 自动格式化：字体字号、缩进、固定行距、页面尺寸、页边距、页面网格、奇偶页动态页码、
  附件、落款和版记等可由 OOXML 确定表达的规则。
- 静态校验：输出可重新打开、附件名称及其他正文和表格内容不变，以及页面、网格、页码
  等属性已写入。附件标签拆段和清单行首布局空白是唯一授权的文字结构规范化。
- 渲染复核：每页是否实际达到 22 行、每行 28 字，标题回行、表格跨页、印章视觉位置，
  以及版记是否落在偶数页最后一面。这些规则没有经过 Word/WPS/LibreOffice 渲染时统一
  报告为“未验证”，不得表述为已经通过。

`dry-run` 只验证输入和返回规则边界，不生成格式化 DOCX。正式和 dry-run 报告都会保留
未验证项摘要；非流式 `message.file` 和流式 `delta.file` 的文件字段保持不变。

## 字体边界

智能体只把目标字体名称写入 DOCX，不在服务端渲染文档，因此服务端无需安装公文字体。
用户端使用 Word/WPS 打开文件时需要安装对应字体；后续若增加服务端 PDF 或图片预览，
再为独立渲染服务配置字体。

## 配置与边界

- `OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES`：输入 DOCX 上限，默认 20 MiB。
- 远程附件继续使用共享的 `AGENT_FILE_ALLOWED_HOSTS`、`AGENT_FILE_MAX_BYTES`、
  `AGENT_FILE_TIMEOUT_SECONDS` 和 `AGENT_FILE_TRANSPORT_OVERRIDES`。
- 当前只支持 DOCX，不接受 DOC、PDF、Markdown 或多文件批处理。
- 不删除日期、重复段落或空段落，不改写正文与表格内容；仅允许将 `附件：首项` 拆成
  标签和首项两个段落，并清理附件项目行首的手工布局空白。
- `公文格式规范.docx` 正文是规则权威来源；其内部文档属性与正文冲突时采用正文值，
  例如右边距采用 `2.6 cm`、行网格采用 `560 twips`。
- 当前规则无法可靠识别的复杂版式按正文处理；如未来增加 LLM，只允许返回段落角色标签，
  不允许生成、修改或删除正文。
