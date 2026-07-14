from pathlib import Path

import pytest

from src.agent_gateway.registry import ModelRegistry, ModelSpec
from src.agent_gateway.supervisor import DevelopmentSupervisor, _free_port, _uvicorn_command


def _registry() -> ModelRegistry:
    return ModelRegistry(
        specs={
            "a": ModelSpec(id="a", app="package.a:app", upstream="http://a:8080"),
            "b": ModelSpec(id="b", app="package.b:app", upstream="http://b:8080"),
        }
    )


def test_supervisor_selects_models_and_assigns_distinct_ports(tmp_path: Path):
    supervisor = DevelopmentSupervisor(_registry(), model_ids=["b"], workspace_root=tmp_path)
    assert [worker.spec.id for worker in supervisor.workers] == ["b"]
    assert supervisor.workers[0].port > 0


def test_supervisor_rejects_unknown_models(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown models"):
        DevelopmentSupervisor(_registry(), model_ids=["missing"], workspace_root=tmp_path)


def test_uvicorn_command_uses_current_python_module_entry():
    command = _uvicorn_command("package.app:app", "127.0.0.1", 9000)
    assert command[-5:] == ["package.app:app", "--host", "127.0.0.1", "--port", "9000"]
    assert command[1:3] == ["-m", "uvicorn"]


def test_free_port_returns_bindable_port():
    assert 0 < _free_port() < 65536
