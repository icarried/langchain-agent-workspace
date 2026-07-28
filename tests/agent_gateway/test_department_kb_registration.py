import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "department-knowledge-base-agent"


def test_department_knowledge_base_is_registered_without_public_worker_port() -> None:
    registry = json.loads(
        (ROOT / "config" / "agent_gateway.json").read_text(encoding="utf-8")
    )
    models = {item["id"]: item for item in registry["models"]}
    assert models[MODEL_ID]["upstream"] == "http://department-knowledge-base:8080"

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    worker = compose["services"]["department-knowledge-base"]
    assert "ports" not in worker
    assert worker["environment"]["KB_NAMESPACE"] == MODEL_ID
    assert worker["depends_on"]["department-kb-minio"]["condition"] == "service_healthy"
    assert "department-knowledge-base" in compose["services"]["gateway"]["depends_on"]
    minio = compose["services"]["department-kb-minio"]
    assert "ports" not in minio
    assert minio["expose"] == ["9000", "9001"]
