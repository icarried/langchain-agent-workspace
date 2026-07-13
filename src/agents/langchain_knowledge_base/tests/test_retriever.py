from kb_api.rag.retriever import Document, RagRetriever
from kb_api.settings import Settings


class FakeVectorStore:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def similarity_search_with_relevance_scores(self, query: str, *, k: int):
        self.calls.append((query, k))
        return self.results


def test_retriever_uses_injected_vectorstore_and_top_k():
    doc = Document(page_content="alpha", metadata={"chunk_id": "c1", "chunk_index": 0, "source": "doc.md"})
    vectorstore = FakeVectorStore([(doc, 0.8)])
    settings = Settings(top_k=2)

    retriever = RagRetriever(vectorstore, settings=settings)

    chunks = retriever.retrieve("what is alpha?", top_k=1)

    assert vectorstore.calls == [("what is alpha?", 1)]
    assert len(chunks) == 1
    assert chunks[0].document == doc
    assert chunks[0].score == 0.8


def test_retriever_clamps_scores_to_schema_bounds():
    high = Document(page_content="high", metadata={"chunk_id": "c1", "chunk_index": 0, "source": "doc.md"})
    low = Document(page_content="low", metadata={"chunk_id": "c2", "chunk_index": 1, "source": "doc.md"})
    vectorstore = FakeVectorStore([(high, 2.4), (low, -1.0)])

    retriever = RagRetriever(vectorstore, settings=Settings())

    chunks = retriever.retrieve("q")

    assert [chunk.score for chunk in chunks] == [1.0, 0.0]
