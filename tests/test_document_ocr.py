import json

import httpx

from src.document_ocr.gpu_stack import GPUStackPaddleOCRVL


def test_gpu_stack_paddleocr_vl_uses_openai_compatible_multimodal_request() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "# OCR result"}}
                ]
            },
        )

    provider = GPUStackPaddleOCRVL(
        model="paddleocr-vl-1.6",
        base_url="http://gpu.example/v1",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = provider.extract_image(b"image", "image/png", source="page-1")

    assert result == "# OCR result"
    assert captured["model"] == "paddleocr-vl-1.6"
    content = captured["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert captured["chat_template_kwargs"]["enable_thinking"] is False
