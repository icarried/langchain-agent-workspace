# ComfyUI Video Generation Agent

工作区原生 LangGraph 文生视频智能体。worker 直接调用 ComfyUI，不依赖额外的 Videos API 服务。

## 数据流

```text
FastGPT / Dify / OpenAI SDK
        -> unified gateway :8008
        -> comfyui-video-generation worker :8080 (internal only)
        -> ComfyUI :8188
```

## 配置

```env
COMFYUI_VIDEO_BASE_URL=http://10.180.26.16:8188
COMFYUI_VIDEO_PUBLIC_BASE_URL=http://10.180.26.16:8188
COMFYUI_VIDEO_MAX_WAIT_SECONDS=1200
COMFYUI_VIDEO_POLL_INTERVAL_SECONDS=2
```

`COMFYUI_VIDEO_BASE_URL` 是 worker 访问地址；`COMFYUI_VIDEO_PUBLIC_BASE_URL` 是平台后端获取生成产物的源地址，不应直接暴露给浏览器。

## 本地 dry-run

```powershell
python -m src.agents.comfyui_video_generation "生成5秒海边骑行视频，1280x720，25fps，随机种子42" --dry-run
```

## 统一网关

```powershell
python -m src.agent_gateway dev --port 8008 --models comfyui-video-generation-agent
```

平台配置：

```text
Base URL: http://<host>:8008/v1
Model: comfyui-video-generation-agent
Stream: enabled
```

显式扩展参数：

```json
{
  "model": "comfyui-video-generation-agent",
  "messages": [{"role": "user", "content": "海边骑行，电影广告质感"}],
  "stream": true,
  "thinking": true,
  "video": {
    "size": "1280x720",
    "seconds": 5,
    "fps": 25,
    "seed": 42,
    "negative_prompt": "cartoon, blurry",
    "prompt_enhance": true
  }
}
```

最终响应正文不再包含 ComfyUI 下载链接；非流式 `message.video` 和流式 `delta.video` 会提供 `source_url`，同时暂时保留旧 `content_url` 字段。AI平台后端必须下载并校验该内部产物，写入自己的 MinIO和文件映射后，再向浏览器返回平台资产地址。
