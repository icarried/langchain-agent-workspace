from __future__ import annotations

import argparse
import json

from .service import generate_image


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversational image generation agent")
    parser.add_argument("prompt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = generate_image(
        [{"role": "user", "content": args.prompt}],
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "text": result.text,
                "mode": result.mode,
                "rewritten_prompt": result.rewritten_prompt,
                "image_url": "<data-url>" if result.image_url.startswith("data:") else result.image_url,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
