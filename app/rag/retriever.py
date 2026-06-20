"""Lightweight BM25-based retrieval over in-memory document chunks.

Replaces the ChromaDB/fastembed vectorstore with a zero-dependency keyword
search so the app stays within Render's 512 MB free-tier memory limit.
"""
import math
import re
from collections import Counter
from langchain_core.documents import Document

from app.rag.store import documents_to_chunks


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_score(query_terms: list[str], doc_tokens: list[str], df: dict[str, int], n_docs: int,
                avgdl: float, k1: float = 1.5, b: float = 0.75) -> float:
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    score = 0.0
    for term in query_terms:
        if term not in tf:
            continue
        idf = math.log((n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5) + 1)
        tf_norm = (tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * dl / max(avgdl, 1)))
        score += idf * tf_norm
    return score


def retrieve(
    _vectorstore,           # kept for API compatibility — ignored
    query: str,
    k: int = 5,
    ticker: str | None = None,
    period_label: str | None = None,
    section_type: str | None = None,
    _docs_override: list | None = None,
) -> list[Document]:
    """BM25 keyword search over in-memory document chunks with optional metadata filters."""
    from app.state import get_documents
    parsed_docs = _docs_override or get_documents()
    all_chunks = documents_to_chunks(parsed_docs)

    # Apply metadata filters
    chunks = [
        c for c in all_chunks
        if (ticker is None or c.metadata.get("ticker") == ticker)
        and (period_label is None or c.metadata.get("period_label") == period_label)
        and (section_type is None or c.metadata.get("section_type") == section_type)
    ]

    if not chunks:
        return []

    query_terms = _tokenize(query)
    tokenized = [_tokenize(c.page_content) for c in chunks]
    avgdl = sum(len(t) for t in tokenized) / len(tokenized)
    df: dict[str, int] = Counter(term for tokens in tokenized for term in set(tokens))

    scores = [
        _bm25_score(query_terms, tokens, df, len(chunks), avgdl)
        for tokens in tokenized
    ]
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in ranked[:k]]


def format_context(documents: list[Document]) -> str:
    """Render retrieved chunks as a labelled context block for an LLM prompt."""
    parts = []
    for doc in documents:
        meta = doc.metadata
        label = f"[{meta.get('ticker')} {meta.get('period_label')} - {meta.get('section_title')}]"
        parts.append(f"{label}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)
