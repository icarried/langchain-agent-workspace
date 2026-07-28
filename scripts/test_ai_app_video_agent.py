"""Test the video agent with the model request used by ai-app-platform."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8008/v1"
DEFAULT_MODEL = "comfyui-video-generation-agent"
DEFAULT_PROMPT = "生成一个猫咪视频"
DOWNLOAD_LINK_PATTERN = re.compile(r"\[下载视频\]\((https?://[^)]+)\)")
FAILURE_MARKERS = (
    "ComfyUI拒绝了工作流",
    "视频生成服务暂时不可用",
    "视频生成失败：",
)


class ModelTestError(RuntimeError):
    """The model request completed unsuccessfully."""


@dataclass(frozen=True, slots=True)
class StreamResult:
    reasoning: str
    content: str
    completed: bool
    video: dict[str, Any] | None = None


def chat_completions_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/chat/completions"):
        return root
    if root.endswith("/v1"):
        return f"{root}/chat/completions"
    return f"{root}/v1/chat/completions"


def iter_sse_data(lines: Iterable[str]) -> Iterator[str]:
    """Parse data blocks from an OpenAI-compatible SSE response."""
    data_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
            data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    if data_lines:
        yield "\n".join(data_lines)


def stream_model_chat(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str | None = None,
    max_wait_seconds: float = 1800,
    on_delta: Callable[[str, str], None] | None = None,
) -> StreamResult:
    url = chat_completions_url(base_url)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "thinking": True,
        "wait_for_completion": True,
        "max_wait_seconds": max_wait_seconds,
    }
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    completed = False
    video: dict[str, Any] | None = None

    with client.stream("POST", url, headers=headers, json=payload) as response:
        if response.status_code >= 400:
            body = response.read()
            raise ModelTestError(
                f"模型请求失败（HTTP {response.status_code}）："
                f"{_body_detail(body, response.headers.get('content-type', ''))}"
            )
        for raw_data in iter_sse_data(response.iter_lines()):
            if raw_data == "[DONE]":
                completed = True
                continue
            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError as exc:
                raise ModelTestError(f"无法解析模型SSE数据：{raw_data[:300]}") from exc
            if not isinstance(event, dict):
                continue
            error = event.get("error")
            if isinstance(error, dict):
                raise ModelTestError(_openai_error(error))
            choices = event.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0]
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict):
                reasoning_delta = delta.get("reasoning_content")
                if reasoning_delta is not None:
                    value = str(reasoning_delta)
                    reasoning_parts.append(value)
                    if on_delta:
                        on_delta("reasoning", value)
                content_delta = delta.get("content")
                if content_delta is not None:
                    value = str(content_delta)
                    content_parts.append(value)
                    if on_delta:
                        on_delta("content", value)
                if isinstance(delta.get("video"), dict):
                    video = delta["video"]
            if choice.get("finish_reason") is not None:
                completed = True

    result = StreamResult(
        reasoning="".join(reasoning_parts),
        content="".join(content_parts),
        completed=completed,
        video=video,
    )
    if not result.completed:
        raise ModelTestError("模型SSE连接已关闭，但没有收到结束事件")
    for marker in FAILURE_MARKERS:
        if marker in result.content:
            raise ModelTestError(result.content.strip())
    return result


def extract_download_url(
    content: str, video: dict[str, Any] | None = None
) -> str | None:
    match = DOWNLOAD_LINK_PATTERN.search(content)
    if match:
        return match.group(1)
    if isinstance(video, dict):
        value = video.get("content_url")
        if isinstance(value, str) and value:
            return value
    return None


def download_video(url: str, output: Path, timeout_seconds: float) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ModelTestError("下载链接不是有效的HTTP(S)地址")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(timeout_seconds, connect=min(30, timeout_seconds)),
            follow_redirects=False,
        ) as response:
            if response.status_code >= 400:
                raise ModelTestError(f"视频下载失败（HTTP {response.status_code}）")
            with output.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
    except httpx.HTTPError as exc:
        raise ModelTestError(f"视频下载失败：{exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按ai-app-platform上游模型协议测试ComfyUI视频Agent"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("VIDEO_AGENT_BASE_URL", DEFAULT_BASE_URL),
        help="统一网关Base URL，默认http://127.0.0.1:8008/v1",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("VIDEO_AGENT_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AGENT_GATEWAY_API_KEY"),
        help="可选；网关未启用鉴权时不需要",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--output", type=Path, help="可选：下载视频到指定路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeout = httpx.Timeout(args.timeout, connect=min(30, args.timeout))
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            request_summary = {
                "url": chat_completions_url(args.base_url),
                "model": args.model,
                "messages": [{"role": "user", "content": args.prompt}],
                "stream": True,
                "thinking": True,
                "wait_for_completion": True,
                "max_wait_seconds": args.timeout,
            }
            print("请求参数：")
            print(json.dumps(request_summary, ensure_ascii=False, indent=2))
            current_channel: str | None = None

            def print_delta(channel: str, value: str) -> None:
                nonlocal current_channel
                if channel != current_channel:
                    label = "推理进度" if channel == "reasoning" else "Agent返回"
                    print(f"\n[{label}]", flush=True)
                    current_channel = channel
                print(value, end="", flush=True)

            result = stream_model_chat(
                client,
                base_url=args.base_url,
                model=args.model,
                prompt=args.prompt,
                api_key=args.api_key,
                max_wait_seconds=args.timeout,
                on_delta=print_delta,
            )
            print()
            download_url = extract_download_url(result.content, result.video)
            if download_url:
                print(f"\n视频地址：{download_url}")
            if args.output:
                if not download_url:
                    raise ModelTestError("Agent响应中没有找到视频下载链接")
                download_video(download_url, args.output, args.timeout)
                print(f"视频已保存：{args.output.resolve()}")
    except (ModelTestError, httpx.HTTPError) as exc:
        print(f"\n测试失败：{exc}", file=sys.stderr)
        return 1
    print("\n测试成功：OpenAI兼容视频模型调用已完成。")
    return 0


def _openai_error(error: dict[str, Any]) -> str:
    message = str(error.get("message") or "模型请求失败")
    code = error.get("code")
    return f"{message}（{code}）" if code else message


def _body_detail(body: bytes, content_type: str) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    if "json" in content_type.lower():
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    return _openai_error(error)[:1000]
                return str(payload.get("detail") or payload)[:1000]
    return text[:1000] or "空响应"


if __name__ == "__main__":
    raise SystemExit(main())
