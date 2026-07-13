import pytest
from pydantic import ValidationError

from kb_api.rag.answer import build_citations
from kb_api.rag.retriever import Document, RetrievedChunk
from kb_api.schemas import Citation


def test_build_citations_from_chunk_metadata():
    chunks = [
        RetrievedChunk(
            document=Document(
                page_content="Evidence text",
                metadata={
                    "chunk_id": "chunk-1",
                    "chunk_index": 3,
                    "source": "kb/source.md",
                    "section": "intro",
                },
            ),
            score=0.91,
        )
    ]

    citations = build_citations(chunks)

    assert len(citations) == 1
    citation = citations[0]
    assert isinstance(citation, Citation)
    assert citation.source == "kb/source.md"
    assert citation.chunk_id == "chunk-1"
    assert citation.chunk_index == 3
    assert citation.score == 0.91
    assert citation.metadata["section"] == "intro"


def test_build_citations_skips_invalid_metadata():
    chunks = [
        RetrievedChunk(
            document=Document(
                page_content="Evidence text",
                metadata={"chunk_index": "bad", "source": "kb/source.md"},
            ),
            score=0.91,
        )
    ]

    assert build_citations(chunks) == []


def test_citation_schema_rejects_scores_out_of_bounds():
    with pytest.raises(ValidationError):
        Citation(
            source="kb/source.md",
            chunk_id="chunk-1",
            chunk_index=0,
            text="evidence",
            score=1.5,
        )
