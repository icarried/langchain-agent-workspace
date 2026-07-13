import pytest

from kb_api.rag.chunking import chunk_documents
from kb_api.rag.loaders import DocumentRecord


def test_chunk_documents_adds_source_and_chunk_index_metadata():
    documents = [DocumentRecord(page_content="abcdefghij", metadata={"source": "doc.txt"})]

    chunks = chunk_documents(documents, chunk_size=4, chunk_overlap=1)

    assert [chunk.page_content for chunk in chunks] == ["abcd", "defg", "ghij"]
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert all(chunk.metadata["source"] == "doc.txt" for chunk in chunks)


def test_chunk_documents_is_stable_for_repeated_runs():
    documents = [DocumentRecord(page_content="abcdefghij", metadata={"source": "doc.txt"})]

    first = chunk_documents(documents, chunk_size=4, chunk_overlap=1)
    second = chunk_documents(documents, chunk_size=4, chunk_overlap=1)

    assert first == second


def test_chunk_documents_skips_blank_documents():
    documents = [DocumentRecord(page_content="   ", metadata={"source": "doc.txt"})]

    assert chunk_documents(documents) == []


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_chunk_documents_validates_parameters(chunk_size: int, chunk_overlap: int):
    with pytest.raises(ValueError):
        chunk_documents(
            [DocumentRecord(page_content="content", metadata={"source": "doc.txt"})],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
