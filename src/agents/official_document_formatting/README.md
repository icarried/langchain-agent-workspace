# official-document-formatting

确定性公文格式化智能体。第一期只执行公司已经验证的 DOCX 格式化规则，不调用大模型，
不做内容润色或改写。

## 能力

- 一次接收一份 DOCX，支持本地路径、HTTP(S) URL、平台 `附件：` 和
  OpenAI content parts 的 `file_url.url`。
- 保留已验证脚本的页面边距、标题识别、字体字号、固定行距、首行缩进、三线表、
  日期清理和重复标题清理规则。
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

## Linux 字体

字体资源位于 `fonts/`，镜像构建时安装到
`/usr/local/share/fonts/official-document/` 并运行 `fc-cache -f`。worker 健康检查
中的 `fonts` 为 `warning` 时仍可格式化 DOCX，但服务端 LibreOffice 渲染可能发生字体替换。

## 配置与边界

- `OFFICIAL_DOCUMENT_FORMATTING_MAX_BYTES`：输入 DOCX 上限，默认 20 MiB。
- 远程附件继续使用共享的 `AGENT_REMOTE_ALLOWED_HOSTS`、`AGENT_REMOTE_MAX_BYTES`、
  `AGENT_REMOTE_TIMEOUT_SECONDS` 和 `AGENT_REMOTE_TRANSPORT_OVERRIDES`。
- 当前只支持 DOCX，不接受 DOC、PDF、Markdown 或多文件批处理。
- 格式化内核保留公司脚本的日期清理和重复标题清理行为；除此之外不增加内容处理。

