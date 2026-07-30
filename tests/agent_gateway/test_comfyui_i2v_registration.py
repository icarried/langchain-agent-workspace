import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "comfyui-image-to-video-agent"


def test_i2v_agent_is_registered_in_gateway_and_compose() -> None:
    registry = json.loads(
        (ROOT / "config" / "agent_gateway.json").read_text(encoding="utf-8")
    )
    entry = next(item for item in registry["models"] if item["id"] == MODEL_ID)
    assert entry["app"] == (
        "src.agents.comfyui_image_to_video.openai_compatible_api:app"
    )
    assert entry["upstream"] == "http://comfyui-image-to-video:8080"

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["comfyui-image-to-video"]
    assert service["expose"] == ["8080"]
    assert "ports" not in service
    assert "src.agents.comfyui_image_to_video.openai_compatible_api:app" in service[
        "command"
    ]
