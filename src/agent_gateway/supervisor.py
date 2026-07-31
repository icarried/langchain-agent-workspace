from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .registry import ModelRegistry, ModelSpec


RESTART_DELAYS = (1, 2, 5, 10, 30)


@dataclass(slots=True)
class WorkerProcess:
    spec: ModelSpec
    port: int
    process: subprocess.Popen | None = None
    failures: int = 0
    started_at: float = 0.0
    restart_at: float = 0.0


class DevelopmentSupervisor:
    def __init__(
        self,
        registry: ModelRegistry,
        *,
        gateway_port: int = 8008,
        model_ids: list[str] | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        selected = model_ids or list(registry.specs)
        unknown = sorted(set(selected) - set(registry.specs))
        if unknown:
            raise ValueError(f"unknown models: {', '.join(unknown)}")
        self.registry = registry
        self.gateway_port = gateway_port
        self.workspace_root = workspace_root or Path(__file__).resolve().parents[2]
        self.workers = [WorkerProcess(registry.specs[model_id], _free_port()) for model_id in selected]
        self.gateway: subprocess.Popen | None = None
        self._stopping = False

    def run(self) -> int:
        try:
            for worker in self.workers:
                self._start_worker(worker)
            self._start_gateway()
            print(f"Agent gateway development entry: http://127.0.0.1:{self.gateway_port}/v1")
            while not self._stopping:
                if self.gateway and self.gateway.poll() is not None:
                    return self.gateway.returncode or 1
                self._restart_failed_workers()
                time.sleep(0.25)
        except KeyboardInterrupt:
            return 0
        finally:
            self.stop()
        return 0

    def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        processes = [worker.process for worker in self.workers if worker.process]
        if self.gateway:
            processes.append(self.gateway)
        for process in processes:
            if process and process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 5
        for process in processes:
            if not process or process.poll() is not None:
                continue
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()

    def _start_worker(self, worker: WorkerProcess) -> None:
        command = _uvicorn_command(worker.spec.app, "127.0.0.1", worker.port)
        worker.process = subprocess.Popen(
            command,
            cwd=self.workspace_root,
            env=_child_environment(),
            creationflags=_creation_flags(),
        )
        worker.started_at = time.monotonic()
        worker.restart_at = 0

    def _start_gateway(self) -> None:
        env = _child_environment()
        env["AGENT_GATEWAY_UPSTREAM_OVERRIDES"] = json.dumps(
            {worker.spec.id: f"http://127.0.0.1:{worker.port}" for worker in self.workers}
        )
        worker_urls = {
            worker.spec.id: f"http://127.0.0.1:{worker.port}"
            for worker in self.workers
        }
        selected_mcp = [
            spec
            for spec in self.registry.mcp_specs.values()
            if spec.model_id in worker_urls
        ]
        env["AGENT_GATEWAY_MCP_UPSTREAM_OVERRIDES"] = json.dumps(
            {
                spec.id: f"{worker_urls[spec.model_id]}/mcp"
                for spec in selected_mcp
                if spec.model_id is not None
            }
        )
        registry_payload = {
            "mcp_servers": [
                {
                    "id": spec.id,
                    "model_id": spec.model_id,
                    "upstream": spec.upstream,
                    "health_upstream": worker_urls[spec.model_id],
                    "default": spec.default,
                }
                for spec in selected_mcp
                if spec.model_id is not None
            ],
            "models": [
                {
                    "id": worker.spec.id,
                    "app": worker.spec.app,
                    "upstream": worker.spec.upstream,
                }
                for worker in self.workers
            ]
        }
        runtime_dir = self.workspace_root / "tmp" / "agent_gateway"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        registry_path = runtime_dir / "dev_registry.json"
        registry_path.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        env["AGENT_GATEWAY_REGISTRY"] = str(registry_path)
        self.gateway = subprocess.Popen(
            _uvicorn_command("src.agent_gateway.app:app", "127.0.0.1", self.gateway_port),
            cwd=self.workspace_root,
            env=env,
            creationflags=_creation_flags(),
        )

    def _restart_failed_workers(self) -> None:
        now = time.monotonic()
        for worker in self.workers:
            if not worker.process or worker.process.poll() is None:
                continue
            if worker.restart_at == 0:
                if now - worker.started_at >= 60:
                    worker.failures = 0
                delay = RESTART_DELAYS[min(worker.failures, len(RESTART_DELAYS) - 1)]
                worker.failures += 1
                worker.restart_at = now + delay
                print(f"Worker {worker.spec.id} stopped; restarting in {delay}s")
            elif now >= worker.restart_at:
                self._start_worker(worker)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _uvicorn_command(app: str, host: str, port: int) -> list[str]:
    return [sys.executable, "-m", "uvicorn", app, "--host", host, "--port", str(port)]


def _child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
