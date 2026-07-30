from __future__ import annotations

import argparse
import asyncio
import json

from src.agents.comfyui_video_generation.client import ComfyUIClient
from src.agents.openai_compatible import OpenAIChatMessage

from .rewriter import GPUStackPromptRewriter
from .schemas import ImageToVideoOptions
from .service import ImageToVideoService
from .settings import ImageToVideoSettings


async def _run(args: argparse.Namespace) -> int:
    settings = ImageToVideoSettings()
    client = ComfyUIClient(
        base_url=settings.comfyui_i2v_base_url,
        public_base_url=settings.public_base_url,
        request_timeout_seconds=settings.comfyui_i2v_request_timeout_seconds,
    )
    try:
        service = ImageToVideoService(
            settings,
            client,
            GPUStackPromptRewriter(settings),
        )
        result = await service.run(
            [OpenAIChatMessage(role="user", content=args.prompt)],
            ImageToVideoOptions(
                size=args.size,
                seconds=args.seconds,
                fps=args.fps,
                seed=args.seed,
            ),
            input_image=args.image,
            dry_run=args.dry_run,
            wait_for_completion=not args.no_wait,
            max_wait_seconds=args.max_wait_seconds,
        )
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0 if result.status not in {"failed"} else 1
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ComfyUI LTX 2.3 image-to-video agent")
    parser.add_argument("prompt")
    parser.add_argument("--image", required=True, help="HTTP(S) or Base64 data URL")
    parser.add_argument("--size")
    parser.add_argument("--seconds", type=int)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-wait-seconds", type=float)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
