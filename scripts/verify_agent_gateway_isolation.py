from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _json_request(url: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 - local verification target
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _chat(base_url: str, model: str) -> tuple[int, dict[str, Any]]:
    return _json_request(
        f"{base_url}/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )


def _compose(compose_file: Path, *args: str) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), *args],
        check=True,
    )


def verify(base_url: str, compose_file: Path) -> None:
    status, models = _json_request(f"{base_url}/v1/models")
    assert status == 200
    expected_count = len(models["data"])
    assert expected_count >= 2, models
    status, batch = _chat(base_url, "batch-resume-review-agent")
    assert status == 200
    assert batch["model"] == "batch-resume-review-agent"
    print(f"before: {expected_count} models and batch worker ready")

    _compose(compose_file, "stop", "contract-review")
    try:
        models: dict[str, Any] = {}
        model_ids: set[str] = set()
        for _ in range(4):
            time.sleep(5)
            status, models = _json_request(f"{base_url}/v1/models")
            assert status == 200
            model_ids = {item["id"] for item in models["data"]}
            if "contract-review-agent" not in model_ids:
                break
        assert len(model_ids) == expected_count - 1, models
        assert "contract-review-agent" not in model_ids
        status, official = _chat(base_url, "official-document-review-agent")
        assert status == 200
        assert official["model"] == "official-document-review-agent"
        status, contract = _chat(base_url, "contract-review-agent")
        assert status == 503, contract
        assert contract["error"]["code"] == "model_unavailable"
        print(
            "during failure: "
            f"{expected_count - 1} models, other worker ready, contract returns 503"
        )
    finally:
        _compose(compose_file, "start", "contract-review")

    time.sleep(12)
    status, models = _json_request(f"{base_url}/v1/models")
    assert status == 200
    assert len(models["data"]) == expected_count, models
    print(f"after recovery: {expected_count} models")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify agent gateway worker fault isolation")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--compose-file", type=Path, default=Path("compose.yaml"))
    args = parser.parse_args()
    verify(args.base_url.rstrip("/"), args.compose_file.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
