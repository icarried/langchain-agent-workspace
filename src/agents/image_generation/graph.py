from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .client import GPUStackClient, GPUStackRequestError
from .inputs import normalize_extracted_source, parse_conversation
from .settings import ImageGenerationSettings


DRY_RUN_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class ImageGenerationState(TypedDict, total=False):
    messages: list[Any]
    dry_run: bool
    instruction: str
    history: str
    image_source: str | None
    image_from_current_user: bool
    image_data_url: str | None
    mode: str
    rewritten_prompt: str
    rewrite_fallback: bool
    generated_image: str
    response_text: str


def build_graph(
    *,
    client: GPUStackClient | None = None,
    settings: ImageGenerationSettings | None = None,
):
    selected_settings = settings or ImageGenerationSettings()
    selected_client = client

    def get_client() -> GPUStackClient:
        nonlocal selected_client
        if selected_client is None:
            selected_client = GPUStackClient(selected_settings)
        return selected_client

    def parse_request(state: ImageGenerationState) -> dict[str, Any]:
        parsed = parse_conversation(
            state["messages"],
            history_limit=selected_settings.image_agent_history_messages,
        )
        return {
            "instruction": parsed.instruction,
            "history": parsed.history,
            "image_source": parsed.image_source,
            "image_from_current_user": parsed.image_from_current_user,
        }

    def select_mode_and_image(state: ImageGenerationState) -> dict[str, Any]:
        source = state.get("image_source")
        image_data_url = (
            normalize_extracted_source(
                source,
                max_bytes=selected_settings.image_agent_max_input_bytes,
            )
            if source
            else None
        )
        return {
            "image_data_url": image_data_url,
            "mode": "edit" if image_data_url else "generate",
        }

    def rewrite_prompt(state: ImageGenerationState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {
                "rewritten_prompt": state["instruction"],
                "rewrite_fallback": False,
            }
        try:
            rewritten = get_client().rewrite_prompt(
                instruction=state["instruction"],
                history=state.get("history", ""),
                image_data_url=state.get("image_data_url"),
            )
        except GPUStackRequestError:
            return {
                "rewritten_prompt": state["instruction"],
                "rewrite_fallback": True,
            }
        return {"rewritten_prompt": rewritten, "rewrite_fallback": False}

    def generate_image_node(state: ImageGenerationState) -> dict[str, Any]:
        if state.get("dry_run"):
            return {"generated_image": DRY_RUN_IMAGE}
        return {
            "generated_image": get_client().generate(
                rewritten_prompt=state["rewritten_prompt"],
                image_data_url=state.get("image_data_url"),
            )
        }

    def build_response(state: ImageGenerationState) -> dict[str, Any]:
        action = "编辑" if state["mode"] == "edit" else "生成"
        suffix = "（提示词改写不可用，已使用原始指令）" if state.get("rewrite_fallback") else ""
        return {"response_text": f"图片已{action}完成。{suffix}"}

    graph = StateGraph(ImageGenerationState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("select_mode_and_image", select_mode_and_image)
    graph.add_node("rewrite_prompt", rewrite_prompt)
    graph.add_node("generate_image", generate_image_node)
    graph.add_node("build_response", build_response)
    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "select_mode_and_image")
    graph.add_edge("select_mode_and_image", "rewrite_prompt")
    graph.add_edge("rewrite_prompt", "generate_image")
    graph.add_edge("generate_image", "build_response")
    graph.add_edge("build_response", END)
    return graph.compile()
