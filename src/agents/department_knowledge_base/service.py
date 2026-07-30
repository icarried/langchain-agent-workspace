from __future__ import annotations

from src.agents.openai_compatible_inputs import AttachmentReference

from .graph import DepartmentKnowledgeBaseRuntime, build_graph
from .schemas import AgentResult, ProgressCallback


class DepartmentKnowledgeBaseAgent:
    def __init__(
        self,
        runtime: DepartmentKnowledgeBaseRuntime | None = None,
    ) -> None:
        self.runtime = runtime or DepartmentKnowledgeBaseRuntime()
        self.graph = build_graph(self.runtime)

    def invoke(
        self,
        *,
        knowledge_id: str,
        text: str,
        sources: list[str | AttachmentReference] | None = None,
        top_k: int | None = None,
        dry_run: bool = False,
        progress: ProgressCallback | None = None,
    ) -> AgentResult:
        state = self.graph.invoke(
            {
                "knowledge_id": knowledge_id,
                "text": text,
                "sources": sources or [],
                "top_k": top_k,
                "dry_run": dry_run,
                "progress": progress,
            }
        )
        return state["result"]
