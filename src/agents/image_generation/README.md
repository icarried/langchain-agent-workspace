# image-generation-agent

面向 AI 应用平台的对话式图片生成与编辑智能体。纯文本请求由
`qwen3.5-122b-a10b` 改写后交给 `qwen-image`；消息中存在图片时改用
`qwen-image-edit`。若当前用户没有上传新图，会沿用最近一条助手消息中的图片。

## 平台接入

- Base URL: `http://<reachable-host>:8008/v1`
- Model: `image-generation-agent`
- Stream: enabled
- 生产鉴权: `AGENT_GATEWAY_API_KEY`

流式请求默认 `thinking=true`。worker会立即在 `delta.reasoning_content` 返回执行
进度，包括解析输入、选择文生图/编辑模式、最终改写提示词、开始生成以及每5秒
心跳；这些内容是可验证的执行状态和提示词产物，不是模型隐藏思维链。最终图片
仍只在一次 `delta.content` 多模态数组中返回。传入 `"thinking": false` 时，
进度改走字符串形式的 `delta.content`。

当前 AI 应用平台仍需按
[`AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md`](../../../docs/development/AI_APP_PLATFORM_IMAGE_OUTPUT_HANDOFF.md)
实现多模态输出持久化和展示，才能完成连续编辑闭环。

## 输入

支持 OpenAI `image_url` content part：

```json
{"type":"image_url","image_url":{"url":"https://example/image.png"}}
```

也支持 `data:image/png;base64,...`，以及：

```json
{
  "type": "image_base64",
  "image_base64": {"mime_type": "image/png", "data": "<base64>"}
}
```

首版每轮只接受一张用户新图，固定生成一张结果图。远程地址受
`AGENT_FILE_ALLOWED_HOSTS`、`AGENT_FILE_TRANSPORT_OVERRIDES` 和图片大小限制约束。

## 调试

```powershell
python -m src.agents.image_generation "画一只坐在窗边的猫" --dry-run
python -m src.agent_gateway dev --port 8008 --models image-generation-agent
```

流式协议示例：

```json
{
  "model": "image-generation-agent",
  "messages": [{"role": "user", "content": "画一只坐在窗边的猫"}],
  "stream": true,
  "thinking": true
}
```
