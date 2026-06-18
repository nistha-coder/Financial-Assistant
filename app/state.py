"""Process-wide cached state: parsed documents and LLM-backed extraction results."""
from functools import lru_cache

from app import config
from app.analysis.tone import analyze_tone
from app.extraction.metrics import extract_financial_metrics
from app.extraction.risks import extract_risk_factors
from app.ingestion.pipeline import load_all_documents
from app.models.schemas import FinancialMetrics, ParsedDocument, RiskFactorList, ToneAnalysis

_documents: list[ParsedDocument] | None = None


def get_documents() -> list[ParsedDocument]:
    global _documents
    if _documents is None:
        _documents = load_all_documents(config.SAMPLE_DATA_DIR)
    return _documents


def add_document(doc: ParsedDocument) -> None:
    """Register a newly-uploaded document and invalidate stale LLM caches."""
    docs = get_documents()
    docs[:] = [
        d for d in docs
        if not (d.ticker == doc.ticker and d.period_label == doc.period_label and d.doc_type == doc.doc_type)
    ]
    docs.append(doc)
    get_metrics.cache_clear()
    get_tone.cache_clear()
    get_risks.cache_clear()


@lru_cache(maxsize=None)
def get_metrics(ticker: str, period_label: str) -> FinancialMetrics:
    return extract_financial_metrics(get_documents(), ticker, period_label)


@lru_cache(maxsize=None)
def get_tone(ticker: str, period_label: str) -> ToneAnalysis:
    return analyze_tone(get_documents(), ticker, period_label)


@lru_cache(maxsize=None)
def get_risks(ticker: str, period_label: str) -> RiskFactorList:
    return extract_risk_factors(get_documents(), ticker, period_label)
