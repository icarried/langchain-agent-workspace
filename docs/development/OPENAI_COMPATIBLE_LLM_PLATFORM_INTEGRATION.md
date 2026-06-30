# OpenAI-compatible 智能体在 FastGPT / Dify 中的接入说明

本文面向使用 FastGPT、Dify 等智能体平台的人，说明如何把一个业务智能体伪装成 OpenAI-compatible LLM，让平台通过“模型 / LLM / AI 对话”节点调用，并把文件链接、岗位要求、业务输入等内容注入给智能体。

## 适用场景

当智能体执行时间较长、需要读取文件、需要流式返回进度和最终报告时，优先考虑 OpenAI-compatible LLM 包装方式。

这种方式适合：

- 平台的普通 HTTP 节点容易超时。
- 不想在工作流里做“提交任务 + 循环轮询”。
- 希望输出直接进入对话界面。
- 平台支持自定义 OpenAI-compatible 模型。
- 文件已经能在平台中生成 HTTP(S) 文件链接，例如 FastGPT 的“文件链接”变量。

不适合：

- 平台不能配置自定义 OpenAI-compatible 模型。
- 平台的 LLM 节点不透传流式输出。
- 业务必须使用 multipart/base64 文件上传，而不是文件链接。

## 服务端启动

以 `batch-resume-review-llm` 为例，启动 OpenAI-compatible 服务：

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

服务提供：

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
```

模型 ID：

```text
batch-resume-review-agent
```

如果你启动的是普通 REST API：

```powershell
uvicorn src.agents.batch_resume_review_llm.api:app --host 0.0.0.0 --port 8006
```

那么 `/v1/models` 和 `/v1/chat/completions` 会返回 404。平台接入时必须启动 `openai_compatible_api:app`。

## 平台模型配置

在 FastGPT / Dify 中新增自定义 OpenAI-compatible 模型时，通常填写：

```text
Base URL: http://<服务可访问地址>:8006/v1
Model: batch-resume-review-agent
API Key: 任意占位值，除非服务端额外启用了鉴权
Stream: 开启
```

注意 Base URL 通常填到 `/v1`，不要填到 `/v1/chat/completions`。

平台会自己拼接：

```text
/chat/completions
```

## Docker / WSL 网络注意事项

如果 FastGPT / Dify 跑在 Docker 容器中，不能直接使用：

```text
http://127.0.0.1:8006/v1
```

因为容器里的 `127.0.0.1` 指的是容器自己，不是 Windows 主机。

如果服务运行在 Windows，而平台运行在 WSL / Docker 中，需要使用容器可访问的地址。例如已经验证过的 WSL `socat` 中继：

```text
http://172.24.0.1:18006/v1
```

验证命令应在平台所在的容器或 WSL 网络环境中执行：

```bash
curl http://172.24.0.1:18006/health
curl http://172.24.0.1:18006/v1/models
```

如果 `/health` 正常，但 `/v1/models` 是 404，说明 8006 上跑错了 FastAPI app。

## 推荐提示词结构

在平台的 LLM / AI 对话节点中，把业务输入整理成清晰的标签区块。

推荐格式：

```text
岗位要求：
{{岗位要求}}

简历文件：
{{文件链接}}

输出要求：
请输出批量简历审查与排序报告。
```

其中：

- `岗位要求` 放 JD 文本。
- `简历文件` 放文件链接数组、文件链接列表或服务端可访问路径。
- `输出要求` 放你希望报告如何输出。

标签建议固定使用：

```text
岗位要求：
简历文件：
输出要求：
```

这样服务端解析最稳定。

## 文件链接注入方式

### 方式一：多行 URL

如果平台能把文件链接渲染成多行，推荐：

```text
简历文件：
http://minio.example/bucket/candidate-a.pdf?X-Amz-Signature=...
http://minio.example/bucket/candidate-b.docx?X-Amz-Signature=...
http://minio.example/bucket/candidate-c.md?X-Amz-Signature=...
```

### 方式二：JSON 数组

FastGPT 的“文件链接”字段可能是 `array<string>`，渲染后类似：

```json
[
  "http://10.71.2.94:9000/fastgpt-private/.../candidate-a.pdf?X-Amz-Signature=...",
  "http://10.71.2.94:9000/fastgpt-private/.../candidate-b.docx?X-Amz-Signature=..."
]
```

也可以直接放在 `简历文件：` 后面：

```text
岗位要求：
要求本科及以上学历，熟悉 Python。

简历文件：
[
  "http://10.71.2.94:9000/fastgpt-private/.../candidate-a.pdf?X-Amz-Signature=...",
  "http://10.71.2.94:9000/fastgpt-private/.../candidate-b.docx?X-Amz-Signature=..."
]

输出要求：
请输出批量简历审查与排序报告。
```

当前 `batch-resume-review-llm` 已兼容这种 JSON 数组格式。

### 方式三：服务端本地路径

如果文件已经在智能体服务端所在机器上，也可以传服务端可访问路径：

```text
简历文件：
E:\data\resumes\candidate-a.pdf
E:\data\resumes\candidate-b.docx
```

这种方式要求路径对运行 `uvicorn` 的服务端进程可见。

## FastGPT 示例

假设 FastGPT 节点里有：

- `岗位要求`: 文本变量
- `文件链接`: `array<string>` 变量

AI 对话节点提示词可写：

```text
你是批量简历审查智能体。请根据岗位要求审查所有简历，输出候选人排序、筛除名单和复核项。

岗位要求：
{{岗位要求}}

简历文件：
{{文件链接}}

输出要求：
请输出 Markdown 格式的批量简历审查与排序报告。
```

模型选择：

```text
batch-resume-review-agent
```

如果 FastGPT 的模型测试只发送 `hello` 一类普通消息，服务会返回“模型已就绪”和提示词格式说明，这是正常的。

## Dify 示例

Dify 中可将该服务配置为 OpenAI-compatible 模型供应商。

模型配置：

```text
Base URL: http://<可访问地址>:8006/v1
Model: batch-resume-review-agent
API Key: 任意占位值
```

`batch-resume-review-llm` 默认开启 `thinking=true`。流式进度会放在 `delta.reasoning_content`，最终报告放在 `delta.content`。如果平台不展示 think/reasoning 内容，可在请求里传 `"thinking": false`，让进度也走普通 content。

工作流中使用 LLM 节点，将上游变量拼入 prompt：

```text
岗位要求：
{{job_description}}

简历文件：
{{resume_file_urls}}

输出要求：
请输出 Markdown 格式的批量简历审查与排序报告。
```

如果 Dify 的文件变量不是 URL，而是文件对象或上传对象，需要先确认是否能取到可由智能体服务端访问的 HTTP URL。当前推荐优先传 URL。

## 常见报错

### connection refused

示例：

```text
dial tcp 127.0.0.1:8006: connect: connection refused
```

原因通常是平台在 Docker 容器中，`127.0.0.1` 指向容器自己。

处理：

- 换成容器可访问的服务地址。
- 如果服务在 Windows，使用已验证的 WSL / Docker 中继地址。
- 在容器内执行 `curl <base-url>/health` 验证。

### /v1/models 返回 404

原因通常是启动了普通 REST API app，而不是 OpenAI-compatible app。

错误启动：

```powershell
uvicorn src.agents.batch_resume_review_llm.api:app --host 0.0.0.0 --port 8006
```

正确启动：

```powershell
uvicorn src.agents.batch_resume_review_llm.openai_compatible_api:app --host 0.0.0.0 --port 8006
```

### POST /v1 返回 404

这是正常的。OpenAI-compatible 服务没有 `POST /v1`。

应测试：

```text
GET  /v1/models
POST /v1/chat/completions
```

平台里的 Base URL 填 `/v1`，平台会自动拼接 `/chat/completions`。

### 模型测试返回 400

如果服务端对普通测试消息返回 400，说明 wrapper 过于严格。

正确行为是：

- 普通测试消息返回 200。
- 返回“模型已就绪”和正式提示词格式说明。
- 只有真正协议格式错误时才返回 400。

当前 `batch-resume-review-llm` 已按这个方式处理。

### 文件 URL 读取失败或 MinIO 404

原因可能是：

- 文件链接已过期。
- 签名 URL 的 Host / 端口指向了错误 MinIO。
- Docker 发布端口和签名端口不一致。
- 服务端无法访问该内网地址。

处理：

- 在智能体服务所在环境中直接 `curl` 文件 URL。
- 确认 MinIO 签名地址和实际发布端口一致。
- 如本工作区中的 FastGPT MinIO 场景，可使用 `BATCH_RESUME_REVIEW_LOCAL_MINIO_ENDPOINT` 做本地传输映射，但必须保留原始签名 Host。

## 手工验证命令

从平台所在容器或 WSL 中验证：

```bash
curl http://172.24.0.1:18006/health

curl http://172.24.0.1:18006/v1/models

curl -H "Content-Type: application/json" \
  -d '{"model":"batch-resume-review-agent","messages":[{"role":"user","content":"hello"}],"stream":false}' \
  http://172.24.0.1:18006/v1/chat/completions
```

正式 dry-run 示例：

```bash
curl -H "Content-Type: application/json" \
  -d '{
    "model": "batch-resume-review-agent",
    "stream": false,
    "thinking": true,
    "dry_run": true,
    "messages": [
      {
        "role": "user",
        "content": "岗位要求：要求本科及以上学历，熟悉 Python。\n\n简历文件：\n[\"http://minio.example/candidate-a.md\",\"http://minio.example/candidate-b.md\"]\n\n输出要求：请输出批量简历审查与排序报告。"
      }
    ]
  }' \
  http://172.24.0.1:18006/v1/chat/completions
```

## 关键经验

- 对平台来说，它调用的是“模型”，不是“业务 API”。所以接口要像模型一样宽容。
- 不要让模型测试因为缺少业务字段失败。
- 文件最好通过 URL 传入，不要指望平台把 PDF/DOCX 二进制按 OpenAI 多模态标准传给自定义模型。
- FastGPT 的文件链接数组要兼容 JSON array 字符串。
- 保留签名 URL 的 query string，不要改写。
- 网络问题优先从容器内 `curl` 验证，不要只在 Windows 本机验证。
- `/health` 通只说明服务通；`/v1/models` 通才说明启动了正确的 OpenAI-compatible app。
