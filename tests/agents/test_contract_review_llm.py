from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.contract_review.openai_compatible_api import (
    ChatCompletionRequest,
    MODEL_ID,
    app,
    parse_contract_request,
)


def _write_contract(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _payload(contract: Path, *, stream: bool) -> dict[str, object]:
    return {
        "model": MODEL_ID,
        "stream": stream,
        "dry_run": True,
        "messages": [
            {
                "role": "user",
                "content": (
                    "委托方角色：甲方\n"
                    "合同类型：技术服务合同\n"
                    "交易背景：甲方采购数据分析平台\n\n"
                    "合同文件：\n"
                    f"{contract}\n\n"
                    "输出要求：请输出合同审查报告。"
                ),
            }
        ],
    }


def test_models_lists_contract_review_agent() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == MODEL_ID


def test_chat_completions_model_probe_without_input() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hello"}], "stream": False},
    )

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "contract-review-agent 已就绪" in content
    assert "合同文件" in content


def test_chat_completions_non_stream_dry_run(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path / "contract.txt", "甲方：A公司\n乙方：B公司\n第一条 服务内容\n")

    response = TestClient(app).post("/v1/chat/completions", json=_payload(contract, stream=False))

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "合同审查 dry-run 报告" in content
    assert "技术服务合同" in content


def test_chat_completions_stream_dry_run(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path / "contract.txt", "甲方：A公司\n第一条 服务内容\n")

    with TestClient(app).stream("POST", "/v1/chat/completions", json=_payload(contract, stream=True)) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "data: [DONE]" in text
    assert "已接收 1 份合同" in text
    assert "reasoning_content" in text
    assert "合同审查 dry-run 报告" in text
    chunks = [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: {")]
    assert any(json.loads(chunk)["object"] == "chat.completion.chunk" for chunk in chunks)


def test_chat_completions_stream_can_disable_thinking(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path / "contract.txt", "甲方：A公司\n第一条 服务内容\n")
    payload = _payload(contract, stream=True)
    payload["thinking"] = False

    with TestClient(app).stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())

    assert "已接收 1 份合同" in text
    assert "reasoning_content" not in text
    assert '"content"' in text


def test_parse_contract_request_accepts_attachment_block() -> None:
    request = ChatCompletionRequest(
        model=MODEL_ID,
        dry_run=True,
        messages=[
            {
                "role": "user",
                "content": (
                    "委托方角色：甲方\n"
                    "交易背景：采购平台开发服务\n\n"
                    "附件：\n"
                    "- 服务合同.docx: http://minio.example/service-contract.docx\n"
                    "输出要求：请输出合同审查报告。"
                ),
            }
        ],
    )

    parsed = parse_contract_request(request)

    assert parsed is not None
    assert parsed.contract_path == "http://minio.example/service-contract.docx"
    assert parsed.transaction_background == "采购平台开发服务"


def test_parse_contract_request_accepts_file_url_content_part() -> None:
    request = ChatCompletionRequest(
        model=MODEL_ID,
        dry_run=True,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "合同类型：技术服务合同"},
                    {
                        "type": "file_url",
                        "file_url": {"url": "http://minio.example/service-contract.pdf"},
                    },
                ],
            }
        ],
    )

    parsed = parse_contract_request(request)

    assert parsed is not None
    assert parsed.contract_path == "http://minio.example/service-contract.pdf"
    assert parsed.contract_type == "技术服务合同"
