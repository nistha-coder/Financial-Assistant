"""Process-wide cached state: parsed documents, the RAG vector store, and
LLM-backed extraction results.

Documents are parsed once at first use and cached in memory. The vector
store is built on first use as well (and persisted to disk so subsequent
runs can reuse it). Extraction/analysis results that involve an LLM call
(financial metrics with guidance, tone analysis) are cached per
ticker/period so repeated API requests don't re-spend free-tier LLM quota.

Documents uploaded at runtime via `/api/upload` are appended to the in-memory
document list, indexed into the vector store incrementally, and any stale
cached extraction results for that ticker/period are invalidated.
"""
from functools import lru_cache

from langchain_chroma import Chroma

from app import config
from app.analysis.tone import analyze_tone
from app.extraction.metrics import extract_financial_metrics
from app.extraction.risks import extract_risk_factors
from app.ingestion.pipeline import load_all_documents
from app.models.schemas import FinancialMetrics, ParsedDocument, RiskFactorList, ToneAnalysis
from app.rag.store import build_vectorstore, documents_to_chunks, get_vectorstore

_documents: list[ParsedDocument] | None = None


def get_documents() -> list[ParsedDocument]:
    global _documents
    if _documents is None:
        _documents = load_all_documents(config.SAMPLE_DATA_DIR)
    return _documents


@lru_cache(maxsize=1)
def get_or_build_vectorstore() -> Chroma:
    try:
        store = get_vectorstore()
        if store._collection.count() > 0:
            return store
    except Exception:
        pass
    return build_vectorstore(get_documents())


def add_document(doc: ParsedDocument) -> None:
    """Register a newly-uploaded document: replace any existing document for
    the same ticker/period/doc_type, index it into the vector store, and
    invalidate any cached extraction results for that ticker/period."""
    docs = get_documents()
    docs[:] = [
        d for d in docs
        if not (d.ticker == doc.ticker and d.period_label == doc.period_label and d.doc_type == doc.doc_type)
    ]
    docs.append(doc)

    get_metrics.cache_clear()
    get_tone.cache_clear()
    get_risks.cache_clear()

    try:
        vectorstore = get_or_build_vectorstore()
        vectorstore.add_documents(documents_to_chunks([doc]))
    except Exception:
        pass


@lru_cache(maxsize=None)
def get_metrics(ticker: str, period_label: str) -> FinancialMetrics:
    return extract_financial_metrics(get_documents(), ticker, period_label)


@lru_cache(maxsize=None)
def get_tone(ticker: str, period_label: str) -> ToneAnalysis:
    return analyze_tone(get_documents(), ticker, period_label)


@lru_cache(maxsize=None)
def get_risks(ticker: str, period_label: str) -> RiskFactorList:
    return extract_risk_factors(get_documents(), ticker, period_label)