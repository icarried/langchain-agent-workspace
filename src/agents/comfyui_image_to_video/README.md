# ComfyUI LTX 2.3 图生视频智能体

模型 ID：`comfyui-image-to-video-agent`。它通过统一网关接收一张图片和自然语言指令，使用视觉 Qwen3.5 改写动作提示词，再把图片上传到 ComfyUI并运行内置的 `video_ltx2_3_i2v.json`。

## 安全边界

- 每次只接受一张图片，支持 HTTP(S)、Base64 data URL和 OpenAI `image_url` content part。
- 图片默认不超过20 MiB，并校验 PNG、JPEG、WebP或GIF真实文件头。
- 时长最多15秒，FPS最多30。
- 尺寸只接受配置白名单，默认：`1280x720`、`720x1280`、`1024x1024`、`1536x864`、`864x1536`、`1920x1080`、`1080x1920`。
- 显式 `video` 参数优先于自然语言；所有参数在提交GPU任务前由服务端再次校验。
- LLM只改写提示词，不能修改服务端确定的尺寸、时长、FPS或seed。
- `dry_run=true` 不下载图片、不调用LLM、不上传图片，也不提交ComfyUI任务。

## OpenAI-compatible 请求

```json
{
  "model": "comfyui-image-to-video-agent",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "让猫咪缓慢转头看向镜头，横屏，5秒，25fps"},
        {"type": "image_url", "image_url": {"url": "https://example/image.png"}}
      ]
    }
  ],
  "stream": true,
  "thinking": true,
  "wait_for_completion": true,
  "video": {"seed": 42}
}
```

也可以使用顶层 `input_image` 传入图片地址。最终非流式 `message.video` 或流式 `delta.video` 包含状态、参数和 ComfyUI源产物地址；AI平台应将源视频持久化到自己的对象存储后再向浏览器公开。

## 调试

```powershell
python -m src.agent_gateway dev --port 8008 --models comfyui-image-to-video-agent
```

生产只通过统一网关 `http://<host>:8008/v1` 调用，worker不发布独立宿主机端口。
