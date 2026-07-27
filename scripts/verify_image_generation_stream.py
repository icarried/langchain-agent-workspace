from __future__ import annotations

import argparse
import json
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify image-generation SSE without printing image data."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8008/v1")
    parser.add_argument("--prompt", default="A blue circle on a white background.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=360)
    args = parser.parse_args()

    payload = {
        "model": "image-generation-agent",
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": True,
        "thinking": True,
        "dry_run": args.dry_run,
    }
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer probe"},
    )
    started = time.monotonic()
    first_delta_seconds: float | None = None
    progress: list[str] = []
    final_content_types: list[str] = []
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line.removeprefix("data: "))
            delta = chunk["choices"][0]["delta"]
            if first_delta_seconds is None:
                first_delta_seconds = time.monotonic() - started
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str):
                progress.append(reasoning.strip())
            content = delta.get("content")
            if isinstance(content, list):
                final_content_types = [
                    str(part.get("type"))
                    for part in content
                    if isinstance(part, dict)
                ]
    print(
        json.dumps(
            {
                "first_delta_seconds": round(first_delta_seconds or 0, 3),
                "progress": progress,
                "final_content_types": final_content_types,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
