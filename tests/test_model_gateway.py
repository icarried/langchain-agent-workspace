from __future__ import annotations

import warnings

from src.model_gateway import GPU_STACK_BASE_URL, gpu_stack_connection, provider_connection


def test_gpu_stack_connection_uses_shared_configuration(monkeypatch) -> None:
    monkeypatch.setenv("GPU_STACK_API_KEY", "gpu-key")
    monkeypatch.setenv("GPU_STACK_BASE_URL", "http://gpu.example/v1/")
    connection = gpu_stack_connection()
    assert connection.api_key == "gpu-key"
    assert connection.base_url == "http://gpu.example/v1"


def test_deepseek_provider_keeps_agent_base_url_override(monkeypatch) -> None:
    monkeypatch.setenv("GPU_STACK_API_KEY", "gpu-key")
    monkeypatch.setenv("AGENT_BASE_URL", "http://override.example/v1")
    connection = provider_connection(
        "deepseek",
        legacy_api_key_env="DEEPSEEK_API_KEY",
        default_base_url=GPU_STACK_BASE_URL,
        base_url_override_env="AGENT_BASE_URL",
    )
    assert connection.api_key == "gpu-key"
    assert connection.base_url == "http://override.example/v1"


def test_legacy_deepseek_key_is_supported_with_deprecation(monkeypatch) -> None:
    monkeypatch.setenv("GPU_STACK_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        connection = gpu_stack_connection()
    assert connection.api_key == "legacy-key"
    assert any(item.category is DeprecationWarning for item in caught)
