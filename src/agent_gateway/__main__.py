from __future__ import annotations

import argparse

import uvicorn

from .registry import ModelRegistry
from .supervisor import DevelopmentSupervisor


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Workspace OpenAI-compatible gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dev = subparsers.add_parser("dev", help="start the gateway and supervised local workers")
    dev.add_argument("--port", type=int, default=8004)
    dev.add_argument(
        "--models",
        default="",
        help="comma-separated model ids; defaults to all registered models",
    )

    serve = subparsers.add_parser("serve", help="start only the gateway for external workers")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8004)

    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("src.agent_gateway.app:app", host=args.host, port=args.port)
        return 0

    models = [item.strip() for item in args.models.split(",") if item.strip()] or None
    return DevelopmentSupervisor(ModelRegistry.load(), gateway_port=args.port, model_ids=models).run()


if __name__ == "__main__":
    raise SystemExit(main())
