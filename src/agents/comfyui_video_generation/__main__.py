from __future__ import annotations

import argparse
import asyncio
import json

from src.agents.openai_compatible import OpenAIChatMessage

from .client import ComfyUIClient
from .schemas import VideoOptions
from .service import VideoGenerationService
from .settings import VideoGenerationSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Direct ComfyUI video generation agent"
    )
    parser.add_argument("prompt")
    parser.add_argument("--size", default=None)
    parser.add_argument("--seconds", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    return parser


async def run(args: argparse.Namespace) -> int:
    settings = VideoGenerationSettings()
    client = ComfyUIClient(settings)
    service = VideoGenerationService(settings, client)
    try:
        result = await service.run(
            [OpenAIChatMessage(role="user", content=args.prompt)],
            VideoOptions(
                size=args.size,
                seconds=args.seconds,
                fps=args.fps,
                seed=args.seed,
            ),
            dry_run=args.dry_run,
            wait_for_completion=not args.no_wait,
            max_wait_seconds=None,
        )
    finally:
        await client.close()
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
