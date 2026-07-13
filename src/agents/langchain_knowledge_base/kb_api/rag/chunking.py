from __future__ import annotations

from kb_api.rag.loaders import DocumentRecord


def chunk_documents(
    documents: list[DocumentRecord],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[DocumentRecord]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be greater than or equal to 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[DocumentRecord] = []
    step = chunk_size - chunk_overlap

    for document in documents:
        text = document.page_content.strip()
        if not text:
            continue

        for chunk_index, start in enumerate(range(0, len(text), step)):
            chunk_text = text[start : start + chunk_size].strip()
            if not chunk_text:
                continue

            metadata = dict(document.metadata)
            metadata["source"] = document.metadata.get("source", "")
            metadata["chunk_index"] = chunk_index

            chunks.append(DocumentRecord(page_content=chunk_text, metadata=metadata))

            if start + chunk_size >= len(text):
                break

    return chunks
