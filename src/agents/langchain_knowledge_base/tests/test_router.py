from kb_api.router import KnowledgeBaseRouter
from kb_api.settings import Settings


def test_router_selects_secondary_by_keyword():
    settings = Settings(
        kb_primary_keywords="product,architecture",
        kb_secondary_keywords="support,policy",
    )
    router = KnowledgeBaseRouter(settings)

    decision = router.route("What is the support policy?")

    assert decision.selected_knowledge_base == "secondary"
    assert "Matched keywords" in decision.reason
    assert {candidate.name for candidate in decision.candidates} == {"primary", "secondary"}


def test_router_honors_requested_knowledge_base():
    router = KnowledgeBaseRouter(Settings())

    decision = router.route("Any question", requested_name="primary")

    assert decision.selected_knowledge_base == "primary"
    assert "Requested" in decision.reason
