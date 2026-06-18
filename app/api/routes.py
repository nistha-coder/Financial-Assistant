"""FastAPI API router — all REST endpoints for the AI Financial Document Analyst.

Endpoints
---------
POST /upload       – Upload a filing / transcript and ingest it
GET  /documents    – List ingested documents
GET  /metrics      – Extract financial metrics for a ticker/period
GET  /compare      – Period-over-period (YoY) metric comparison
GET  /tone         – Management tone / sentiment analysis
GET  /risks        – Risk factor extraction
GET  /benchmark    – Peer competitor benchmarking table
POST /memo         – Generate an investment memo
GET  /ask          – RAG-powered question answering
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app import config
from app.analysis.tone import compare_tone
from app.benchmarking.benchmark import build_benchmark_table
from app.extraction.comparison import compute_metric_comparison
from app.ingestion.parser import parse_document
from app.memo.generator import generate_investment_memo
from app.rag.retriever import format_context, retrieve
from app.state import (
    add_document,
    get_documents,
    get_metrics,
    get_or_build_vectorstore,
    get_risks,
    get_tone,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_params(ticker: str | None, period: str | None) -> tuple[str, str]:
    """Validate that both ticker and period query params are present."""
    if not ticker or not period:
        raise HTTPException(status_code=400, detail="Both 'ticker' and 'period' query parameters are required.")
    return ticker, period


# ---------------------------------------------------------------------------
# POST /upload — Ingest a new filing / transcript
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    period: str = Form(...),
    doc_type: str = Form(...),
):
    """Accept a .txt or .pdf upload, save it to the sample filings directory,
    parse it, and register it in the in-memory document store."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".txt", ".pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'. Only .txt and .pdf are accepted.")

    # Normalise doc_type for the filename convention used by the parser
    dtype_map = {"10-K": "10K", "10-Q": "10K", "10K": "10K", "earnings_call": "earnings_call"}
    dtype_key = dtype_map.get(doc_type, doc_type)

    # Save to data/sample_filings/{TICKER}_FY{YEAR}_{doctype}.{ext}
    dest_dir = config.SAMPLE_DATA_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{ticker.upper()}_{period}_{dtype_key}{suffix}"
    dest_path = dest_dir / filename

    # Write uploaded content to disk
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        doc = parse_document(dest_path)
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse uploaded file: {exc}")

    add_document(doc)

    return {
        "status": "success",
        "message": f"Uploaded and ingested {filename}",
        "document": {
            "company": doc.company,
            "ticker": doc.ticker,
            "period_label": doc.period_label,
            "doc_type": doc.doc_type,
        },
    }


# ---------------------------------------------------------------------------
# GET /documents — List loaded documents
# ---------------------------------------------------------------------------

@router.get("/documents")
def list_documents():
    """Return metadata for every ingested document."""
    docs = get_documents()
    return [
        {
            "company": d.company,
            "ticker": d.ticker,
            "period_label": d.period_label,
            "period_type": d.period_type,
            "doc_type": d.doc_type,
            "fiscal_year": d.fiscal_year,
        }
        for d in docs
    ]


# ---------------------------------------------------------------------------
# GET /metrics — Financial metric extraction
# ---------------------------------------------------------------------------

@router.get("/metrics")
def metrics(ticker: str = Query(None), period: str = Query(None)):
    ticker, period = _require_params(ticker, period)
    try:
        result = get_metrics(ticker, period)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /compare — Period-over-period comparison
# ---------------------------------------------------------------------------

@router.get("/compare")
def compare(
    ticker: str = Query(None),
    current_period: str = Query(None),
    prior_period: str = Query(None),
):
    if not ticker or not current_period or not prior_period:
        raise HTTPException(
            status_code=400,
            detail="'ticker', 'current_period', and 'prior_period' are all required.",
        )
    try:
        current_metrics = get_metrics(ticker, current_period)
        prior_metrics = get_metrics(ticker, prior_period)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    comparison = compute_metric_comparison(current_metrics, prior_metrics, comparison_type="YoY")
    return comparison.model_dump()


# ---------------------------------------------------------------------------
# GET /tone — Management tone analysis
# ---------------------------------------------------------------------------

@router.get("/tone")
def tone(ticker: str = Query(None), period: str = Query(None)):
    ticker, period = _require_params(ticker, period)
    try:
        result = get_tone(ticker, period)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /risks — Risk factor extraction
# ---------------------------------------------------------------------------

@router.get("/risks")
def risks(ticker: str = Query(None), period: str = Query(None)):
    ticker, period = _require_params(ticker, period)
    try:
        result = get_risks(ticker, period)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /benchmark — Peer benchmarking table
# ---------------------------------------------------------------------------

@router.get("/benchmark")
def benchmark(
    tickers: str = Query(None, description="Comma-separated tickers, e.g. TVIZ,GNRG,HLTH"),
    period: str = Query(None),
):
    if not tickers or not period:
        raise HTTPException(status_code=400, detail="Both 'tickers' and 'period' are required.")

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="At least one ticker is required.")

    docs = get_documents()
    try:
        table = build_benchmark_table(
            docs,
            ticker_list,
            period,
            metrics_fn=lambda _docs, t, p: get_metrics(t, p),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return table.model_dump()


# ---------------------------------------------------------------------------
# POST /memo — Investment memo generation
# ---------------------------------------------------------------------------

@router.post("/memo")
def memo(
    ticker: str = Query(None),
    period: str = Query(None),
    peers: Optional[str] = Query(None, description="Comma-separated peer tickers"),
):
    ticker, period = _require_params(ticker, period)
    peer_list = [t.strip().upper() for t in peers.split(",") if t.strip()] if peers else None
    docs = get_documents()

    try:
        result = generate_investment_memo(docs, ticker, period, peer_tickers=peer_list)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result.model_dump()


# ---------------------------------------------------------------------------
# GET /ask — RAG Q&A
# ---------------------------------------------------------------------------

@router.get("/ask")
def ask(
    question: str = Query(..., description="Natural-language question about the filings"),
    ticker: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
):
    """Answer a question using retrieval-augmented generation over the
    ingested financial documents."""
    if not question.strip():
        raise HTTPException(status_code=400, detail="'question' cannot be empty.")

    try:
        vectorstore = get_or_build_vectorstore()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Vector store unavailable: {exc}")

    chunks = retrieve(vectorstore, question, k=5, ticker=ticker, period_label=period)

    if not chunks:
        return {"answer": "No relevant information found in the ingested documents.", "sources": []}

    context = format_context(chunks)

    from app.llm import get_llm

    prompt = (
        "You are an expert financial analyst. Use ONLY the context below to answer "
        "the question. If the context does not contain enough information, say so.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )

    try:
        llm = get_llm(temperature=0.1)
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    sources = [
        {
            "ticker": c.metadata.get("ticker"),
            "period_label": c.metadata.get("period_label"),
            "section": c.metadata.get("section_title"),
        }
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}
