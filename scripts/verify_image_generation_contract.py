from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def post_json(url: str, payload: dict, *, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer probe"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = None
        raise RuntimeError(
            f"HTTP {exc.code}: {detail or 'upstream request failed'}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError("response is not a JSON object")
    return value


def content_parts(response: dict) -> list[dict]:
    content = response["choices"][0]["message"]["content"]
    if not isinstance(content, list):
        raise RuntimeError("assistant content is not a multimodal array")
    return [part for part in content if isinstance(part, dict)]


def image_url(parts: list[dict]) -> str:
    images = [
        part.get("image_url", {}).get("url")
        for part in parts
        if part.get("type") == "image_url"
        and isinstance(part.get("image_url"), dict)
    ]
    if len(images) != 1 or not isinstance(images[0], str):
        raise RuntimeError("response does not contain exactly one image")
    if not images[0].startswith(("data:image/", "http://", "https://")):
        raise RuntimeError("response image reference is invalid")
    return images[0]


def summarize(parts: list[dict], image: str) -> dict:
    return {
        "content_types": [part.get("type") for part in parts],
        "image_transport": "data_url" if image.startswith("data:image/") else "url",
        "image_reference_length": len(image),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a redacted two-turn image generation/edit contract probe."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8008/v1")
    parser.add_argument("--timeout", type=float, default=360)
    args = parser.parse_args()
    endpoint = args.base_url.rstrip("/") + "/chat/completions"

    first = post_json(
        endpoint,
        {
            "model": "image-generation-agent",
            "messages": [
                {
                    "role": "user",
                    "content": "A single blue circle centered on a plain white background.",
                }
            ],
            "stream": False,
        },
        timeout=args.timeout,
    )
    first_parts = content_parts(first)
    first_image = image_url(first_parts)
    print(
        json.dumps(
            {"generation": summarize(first_parts, first_image)},
            ensure_ascii=False,
        ),
        flush=True,
    )

    second = post_json(
        endpoint,
        {
            "model": "image-generation-agent",
            "messages": [
                {"role": "assistant", "content": first_parts},
                {
                    "role": "user",
                    "content": "Change only the circle from blue to red.",
                },
            ],
            "stream": False,
        },
        timeout=args.timeout,
    )
    second_parts = content_parts(second)
    second_image = image_url(second_parts)
    print(
        json.dumps(
            {
                "generation": summarize(first_parts, first_image),
                "continuous_edit": summarize(second_parts, second_image),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
