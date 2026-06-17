"""Filtered similarity search helpers over the financial document vector store."""
from langchain_chroma import Chroma
from langchain_core.documents import Document


def retrieve(
    vectorstore: Chroma,
    query: str,
    k: int = 5,
    ticker: str | None = None,
    period_label: str | None = None,
    section_type: str | None = None,
) -> list[Document]:
    """Run a similarity search, optionally filtered by company/period/section."""
    conditions = []
    if ticker:
        conditions.append({"ticker": ticker})
    if period_label:
        conditions.append({"period_label": period_label})
    if section_type:
        conditions.append({"section_type": section_type})

    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    return vectorstore.similarity_search(query, k=k, filter=where)


def format_context(documents: list[Document]) -> str:
    """Render retrieved chunks as a labelled context block for an LLM prompt."""
    parts = []
    for doc in documents:
        meta = doc.metadata
        label = f"[{meta.get('ticker')} {meta.get('period_label')} - {meta.get('section_title')}]"
        parts.append(f"{label}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)