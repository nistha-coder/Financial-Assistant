"""FastAPI API router — all REST endpoints for the AI Financial Document Analyst."""
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app import config
from app.analysis.tone import analyze_tone, compare_tone
from app.benchmarking.benchmark import build_benchmark_table
from app.extraction.comparison import compute_metric_comparison
from app.extraction.metrics import extract_financial_metrics
from app.extraction.risks import compare_risk_factors, extract_risk_factors
from app.ingestion.parser import parse_document
from app.ingestion.pipeline import get_document
from app.llm import get_llm
from app.memo.generator import generate_investment_memo
from app.models.schemas import (
    BenchmarkTable,
    FinancialMetrics,
    InvestmentMemo,
    MetricComparison,
    RiskComparison,
    RiskFactorList,
    ToneAnalysis,
    ToneComparison,
)
from app.rag.retriever import format_context, retrieve
from app.state import add_document, get_documents, get_metrics, get_or_build_vectorstore, get_risks, get_tone

router = APIRouter()

UPLOAD_DIR = config.BASE_DIR / "data" / "uploads"


class CompanyPeriod(BaseModel):
    company: str
    ticker: str
    period_label: str
    fiscal_year: int
    doc_type: str


def _get_doc_or_404(ticker: str, period_label: str):
    doc = get_document(get_documents(), ticker, period_label)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document found for {ticker} {period_label}")
    return doc


def _prior_period_label(period_label: str) -> str | None:
    if period_label.startswith("FY") and period_label[2:].isdigit():
        return f"FY{int(period_label[2:]) - 1}"
    return None


# ---------------------------------------------------------------------------
# GET /companies — list all loaded companies/periods
# ---------------------------------------------------------------------------

@router.get("/companies", response_model=list[CompanyPeriod])
def list_companies() -> list[CompanyPeriod]:
    seen: dict[tuple[str, str], CompanyPeriod] = {}
    for doc in get_documents():
        key = (doc.ticker, doc.period_label)
        if key not in seen:
            seen[key] = CompanyPeriod(
                company=doc.company,
                ticker=doc.ticker,
                period_label=doc.period_label,
                fiscal_year=doc.fiscal_year,
                doc_type=doc.doc_type,
            )
    return list(seen.values())


# ---------------------------------------------------------------------------
# POST /upload — ingest a new filing
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    company: str
    ticker: str
    period_label: str
    doc_type: str
    sections: list[str]


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    fiscal_year: int = Form(...),
    doc_type: str = Form(...),
) -> UploadResponse:
    if doc_type not in ("10-K", "earnings_call"):
        raise HTTPException(status_code=400, detail="doc_type must be '10-K' or 'earnings_call'")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".pdf", ".txt"):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    doctype_token = "10K" if doc_type == "10-K" else "earnings_call"
    ticker = ticker.strip().upper()
    if not ticker.isalnum():
        raise HTTPException(status_code=400, detail="Ticker must be alphanumeric")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{ticker}_FY{fiscal_year}_{doctype_token}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        parsed = parse_document(dest)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not parse document: {exc}") from exc

    add_document(parsed)

    return UploadResponse(
        company=parsed.company,
        ticker=parsed.ticker,
        period_label=parsed.period_label,
        doc_type=parsed.doc_type,
        sections=[s.section_type for s in parsed.sections],
    )


# ---------------------------------------------------------------------------
# GET /metrics/{ticker}/{period_label}
# ---------------------------------------------------------------------------

@router.get("/metrics/{ticker}/{period_label}", response_model=FinancialMetrics)
def get_metrics_endpoint(ticker: str, period_label: str) -> FinancialMetrics:
    _get_doc_or_404(ticker, period_label)
    return get_metrics(ticker, period_label)


# ---------------------------------------------------------------------------
# GET /metrics/{ticker}/{period_label}/comparison
# ---------------------------------------------------------------------------

@router.get("/metrics/{ticker}/{period_label}/comparison", response_model=MetricComparison)
def get_metrics_comparison(ticker: str, period_label: str, prior_period: str | None = None) -> MetricComparison:
    _get_doc_or_404(ticker, period_label)
    prior = prior_period or _prior_period_label(period_label)
    if not prior:
        raise HTTPException(status_code=400, detail="Could not determine prior period; pass ?prior_period=")
    _get_doc_or_404(ticker, prior)
    current_m = get_metrics(ticker, period_label)
    prior_m = get_metrics(ticker, prior)
    comparison_type = "YoY" if current_m.period_type == "annual" else "QoQ"
    return compute_metric_comparison(current_m, prior_m, comparison_type=comparison_type)


# ---------------------------------------------------------------------------
# GET /tone/{ticker}/{period_label}
# ---------------------------------------------------------------------------

@router.get("/tone/{ticker}/{period_label}", response_model=ToneAnalysis)
def get_tone_endpoint(ticker: str, period_label: str) -> ToneAnalysis:
    _get_doc_or_404(ticker, period_label)
    return get_tone(ticker, period_label)


# ---------------------------------------------------------------------------
# GET /tone/{ticker}/{period_label}/comparison
# ---------------------------------------------------------------------------

@router.get("/tone/{ticker}/{period_label}/comparison", response_model=ToneComparison)
def get_tone_comparison(ticker: str, period_label: str, prior_period: str | None = None) -> ToneComparison:
    _get_doc_or_404(ticker, period_label)
    prior = prior_period or _prior_period_label(period_label)
    if not prior:
        raise HTTPException(status_code=400, detail="Could not determine prior period; pass ?prior_period=")
    _get_doc_or_404(ticker, prior)
    current_t = get_tone(ticker, period_label)
    prior_t = get_tone(ticker, prior)
    return compare_tone(current_t, prior_t)


# ---------------------------------------------------------------------------
# GET /risks/{ticker}/{period_label}
# ---------------------------------------------------------------------------

@router.get("/risks/{ticker}/{period_label}", response_model=RiskFactorList)
def get_risks_endpoint(ticker: str, period_label: str) -> RiskFactorList:
    _get_doc_or_404(ticker, period_label)
    return get_risks(ticker, period_label)


# ---------------------------------------------------------------------------
# GET /risks/{ticker}/{period_label}/comparison
# ---------------------------------------------------------------------------

@router.get("/risks/{ticker}/{period_label}/comparison", response_model=RiskComparison)
def get_risk_comparison(ticker: str, period_label: str, prior_period: str | None = None) -> RiskComparison:
    _get_doc_or_404(ticker, period_label)
    prior = prior_period or _prior_period_label(period_label)
    if not prior:
        raise HTTPException(status_code=400, detail="Could not determine prior period; pass ?prior_period=")
    _get_doc_or_404(ticker, prior)
    current_r = get_risks(ticker, period_label)
    prior_r = get_risks(ticker, prior)
    return compare_risk_factors(current_r, prior_r)


# ---------------------------------------------------------------------------
# GET /benchmark/{period_label}
# ---------------------------------------------------------------------------

@router.get("/benchmark/{period_label}", response_model=BenchmarkTable)
def get_benchmark(period_label: str, tickers: str = Query(...)) -> BenchmarkTable:
    docs = get_documents()
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="Provide at least one ticker")
    table = build_benchmark_table(docs, ticker_list, period_label, metrics_fn=lambda _docs, t, p: get_metrics(t, p))
    if not table.rows:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker_list} in {period_label}")
    return table


# ---------------------------------------------------------------------------
# GET /memo/{ticker}/{period_label}
# ---------------------------------------------------------------------------

@router.get("/memo/{ticker}/{period_label}", response_model=InvestmentMemo)
def get_memo(ticker: str, period_label: str, peers: str | None = Query(default=None)) -> InvestmentMemo:
    docs = get_documents()
    _get_doc_or_404(ticker, period_label)
    peer_tickers = [t.strip().upper() for t in peers.split(",") if t.strip()] if peers else None
    return generate_investment_memo(docs, ticker, period_label, peer_tickers=peer_tickers)


# ---------------------------------------------------------------------------
# POST /rag/query
# ---------------------------------------------------------------------------

class RagQueryRequest(BaseModel):
    query: str
    ticker: str | None = None
    period_label: str | None = None
    section_type: str | None = None
    k: int = 5


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[str]


@router.post("/rag/query", response_model=RagQueryResponse)
def rag_query(request: RagQueryRequest) -> RagQueryResponse:
    vectorstore = get_or_build_vectorstore()
    documents = retrieve(
        vectorstore,
        request.query,
        k=request.k,
        ticker=request.ticker,
        period_label=request.period_label,
        section_type=request.section_type,
    )
    if not documents:
        raise HTTPException(status_code=404, detail="No relevant context found")

    context = format_context(documents)
    prompt = (
        "Answer the question using ONLY the context below. If the context does not "
        "contain the answer, say so explicitly.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {request.query}"
    )
    llm = get_llm(temperature=config.LLM_TEMPERATURE_ANALYSIS)
    response = llm.invoke(prompt)

    sources = [
        f"{doc.metadata.get('ticker')} {doc.metadata.get('period_label')} - {doc.metadata.get('section_title')}"
        for doc in documents
    ]
    return RagQueryResponse(answer=response.content, sources=sources)
