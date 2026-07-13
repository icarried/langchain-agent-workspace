from __future__ import annotations

from dataclasses import dataclass

from kb_api.schemas import KnowledgeBaseInfo, RouteDecision
from kb_api.settings import KnowledgeBaseConfig, Settings


@dataclass(slots=True)
class KnowledgeBaseRouter:
    settings: Settings

    def route(self, question: str, requested_name: str | None = None) -> RouteDecision:
        knowledge_bases = self.settings.knowledge_bases()
        candidates = [_to_info(kb) for kb in knowledge_bases]

        if requested_name:
            selected = self._find_by_name(knowledge_bases, requested_name)
            return RouteDecision(
                selected_knowledge_base=selected.name,
                reason=f"Requested knowledge base '{requested_name}'.",
                candidates=candidates,
            )

        normalized = question.lower()
        scored = [
            (self._score(normalized, kb), kb)
            for kb in knowledge_bases
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, selected = scored[0]
        reason = (
            f"Matched keywords for '{selected.name}'."
            if best_score > 0
            else f"No keyword match; using default knowledge base '{selected.name}'."
        )
        return RouteDecision(
            selected_knowledge_base=selected.name,
            reason=reason,
            candidates=candidates,
        )

    def selected_config(self, decision: RouteDecision) -> KnowledgeBaseConfig:
        return self._find_by_name(self.settings.knowledge_bases(), decision.selected_knowledge_base)

    @staticmethod
    def _score(question: str, kb: KnowledgeBaseConfig) -> int:
        score = sum(1 for keyword in kb.keywords if keyword and keyword in question)
        description_terms = {
            term.strip(".,:;()[]{}").lower()
            for term in kb.description.split()
            if len(term.strip(".,:;()[]{}")) > 3
        }
        score += sum(1 for term in description_terms if term in question)
        return score

    @staticmethod
    def _find_by_name(knowledge_bases: list[KnowledgeBaseConfig], name: str) -> KnowledgeBaseConfig:
        for kb in knowledge_bases:
            if kb.name == name:
                return kb
        known = ", ".join(kb.name for kb in knowledge_bases)
        raise ValueError(f"Unknown knowledge base '{name}'. Known knowledge bases: {known}")


def _to_info(kb: KnowledgeBaseConfig) -> KnowledgeBaseInfo:
    return KnowledgeBaseInfo(
        name=kb.name,
        description=kb.description,
        docs_dir=str(kb.docs_dir),
        collection=kb.chroma_collection,
        keywords=kb.keywords,
    )
