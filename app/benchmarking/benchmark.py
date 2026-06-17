"""Cross-company competitor benchmarking.

Builds a single comparison table across multiple companies for a given
period, covering scale (revenue), growth (YoY revenue growth), profitability
(margins), and capital allocation (capex intensity, leverage). All figures
are derived deterministically from `FinancialMetrics` already produced by
`app.extraction.metrics`.
"""
from app.extraction.metrics import extract_financial_metrics
from app.ingestion.pipeline import get_document
from app.models.schemas import BenchmarkRow, BenchmarkTable, FinancialMetrics, ParsedDocument


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return round((current - prior) / prior * 100, 1)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 2)


def _build_row(metrics: FinancialMetrics, prior_metrics: FinancialMetrics | None) -> BenchmarkRow:
    return BenchmarkRow(
        company=metrics.company,
        ticker=metrics.ticker,
        period_label=metrics.period_label,
        revenue=metrics.revenue,
        revenue_growth_yoy_pct=_pct_change(metrics.revenue, prior_metrics.revenue if prior_metrics else None),
        ebitda_margin_pct=metrics.ebitda_margin_pct,
        operating_margin_pct=metrics.operating_margin_pct,
        net_margin_pct=metrics.net_margin_pct,
        capex_pct_of_revenue=(
            round(metrics.capex / metrics.revenue * 100, 1)
            if metrics.capex is not None and metrics.revenue
            else None
        ),
        debt_to_ebitda=_ratio(metrics.total_debt, metrics.ebitda),
    )


def _prior_period_label(period_label: str) -> str | None:
    """Derive the prior annual period label, e.g. 'FY2024' -> 'FY2023'."""
    if period_label.startswith("FY") and period_label[2:].isdigit():
        return f"FY{int(period_label[2:]) - 1}"
    return None


def build_benchmark_table(
    docs: list[ParsedDocument],
    tickers: list[str],
    period_label: str,
    metrics_fn=extract_financial_metrics,
) -> BenchmarkTable:
    """Build a benchmark table comparing the given companies for one period.

    `metrics_fn(docs, ticker, period_label) -> FinancialMetrics` defaults to
    `extract_financial_metrics` but can be swapped for a cached accessor
    (e.g. `app.state.get_metrics`) to avoid redundant LLM calls.
    """
    prior_label = _prior_period_label(period_label)

    rows: list[BenchmarkRow] = []
    for ticker in tickers:
        if get_document(docs, ticker, period_label) is None:
            continue
        metrics = metrics_fn(docs, ticker, period_label)
        prior_metrics = None
        if prior_label and get_document(docs, ticker, prior_label) is not None:
            prior_metrics = metrics_fn(docs, ticker, prior_label)
        rows.append(_build_row(metrics, prior_metrics))

    return BenchmarkTable(period_label=period_label, rows=rows)
