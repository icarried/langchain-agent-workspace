# AI 应用平台图片输出 Handoff

## 目标

让 AI 应用平台完整消费 `image-generation-agent` 的 OpenAI-compatible 多模态
Chat Completions 输出：展示生成图、持久化到现有 MinIO/file mapping，并在下一轮
对话自动把最近生成图传回智能体。本工作区只提供智能体协议；平台修改应在
`ai-app-platform` 仓库完成。

## 上游协议

```text
Base URL: http://172.27.0.1:8008/v1
Model: image-generation-agent
Stream: enabled
附件 mode: image_url
附件 image_transport: data_url
```

非流式 `choices[0].message.content`、流式最终
`choices[0].delta.content` 都可能是：

```json
[
  {"type": "text", "text": "图片已生成完成。"},
  {
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,..."}
  }
]
```

`image_url.url` 也可能是 HTTP(S) 临时地址。进度通过
`delta.reasoning_content` 返回，包括模式选择、最终改写提示词、开始生成和
每5秒心跳；这是执行状态而非模型隐藏思维链。平台应收到一条就立即向前端转发，
不要等图片 content数组到达后再批量刷新。

## 后端修改

1. 扩展 `backend/src/services/llm_service.py`：
   - 字符串 `delta.content` 保持原 `delta` 事件。
   - 数组 content 逐项处理 `text` 与 `image_url`。
   - `text` 转为原 `delta`；图片进入持久化流程。
2. 图片持久化必须在后端完成：
   - data URL验证 MIME、Base64、原始字节大小和真实图片格式。
   - HTTP(S) URL设置连接/读取超时、最大响应、重定向和主机策略。
   - 校验像素上限，生成安全文件名，写入现有 MinIO和 file mapping。
   - 不记录原始 Base64、完整签名 URL或鉴权头。
3. 持久化成功后向前端发送：

```text
event: image_delta
data: {"file_id":"uuid","filename":"generated.png","file_type":"image","mime_type":"image/png","url":"<new presigned url>"}
```

4. 非流式连接测试中的 `_extract_chat_content` 应能从 content 数组提取 `text`；
   只有图片而没有文本也应判定为有效响应。
5. 单张图片持久化失败时发送 `error` 并结束该轮，不能把不可恢复的临时 URL当成功。

## 前端修改

1. `frontend/src/api/llmModels.ts` 的 `StreamHandlers` 增加
   `onImageDelta(attachment)`，SSE解析新增 `image_delta`。
2. `ChatBubble` 继续使用现有 `attachments`：
   - 收到 `image_delta` 后追加到当前助手 bubble。
   - 图片使用画廊/卡片展示，并支持预览、下载和错误占位。
3. `buildRequestMessages` 保留助手附件。下一轮发送时后端按模型
   `adapter_config` 重新签发 URL或生成 data URL。
4. 当前用户上传新图仍作为用户附件发送；智能体会让新图覆盖历史助手图。
5. 浏览器状态只保存 `file_id` 和展示元数据，不保存原始 Base64。

## 测试与验收

- 后端单测：字符串/数组 content、URL/data URL、错误 MIME、超限、下载超时、
  MinIO失败、连接测试只有图片。
- 前端单测：`image_delta` 解析、图片 bubble、重试、上下文裁剪后保留助手附件。
- 端到端：
  1. 纯文本生成一张图并展示。
  2. 刷新预签名 URL后图片仍可访问。
  3. 输入“再亮一点”，确认不重新上传也能编辑上一张图。
  4. 上传一张新图，确认新图覆盖历史底图。
  5. 分别验证 HTTP URL和 Base64 data URL结果。

实现后同步更新平台的 `docs/llm_chat_capabilities.md` 与
`docs/model_gateway_chat_completions_reference.md`，移除“只能展示文本输出”的限制。
