"""Generate a structured investment memo grounded in extracted financial data.

The memo's narrative sections (overview, bull/bear case, key risks, questions)
are produced by an LLM, but the prompt is built entirely from data we have
already extracted deterministically (financial metrics, period-over-period
comparisons, management tone, risk factor changes, and peer benchmarking).
This keeps the narrative grounded in real, verified figures rather than
relying on the LLM to recall or invent numbers.
"""
from pydantic import BaseModel, Field

from app import config
from app.analysis.tone import compare_tone
from app.benchmarking.benchmark import build_benchmark_table
from app.extraction.comparison import compute_metric_comparison
from app.extraction.risks import compare_risk_factors
from app.ingestion.pipeline import get_document, get_section_text
from app.llm import get_llm, invoke_structured
from app.models.schemas import InvestmentMemo, ParsedDocument
from app.state import get_metrics, get_risks, get_tone


class _ExtractedMemo(BaseModel):
    company_overview: str = Field(description="2-4 sentence overview of the company's business and segment")
    financial_summary: str = Field(description="3-5 sentence summary of financial performance and trajectory")
    bull_case: list[str] = Field(description="3-5 bullet points supporting a positive investment thesis, grounded in the provided data")
    bear_case: list[str] = Field(description="3-5 bullet points supporting a negative investment thesis, grounded in the provided data")
    key_risks: list[str] = Field(description="3-5 bullet points on the most material risk factors")
    questions_to_investigate: list[str] = Field(description="3-5 follow-up due-diligence questions an analyst should investigate further")


MEMO_PROMPT = """You are a buy-side equity research analyst writing an investment memo for \
{company} ({ticker}), covering {period_label}. Use ONLY the data below -- every claim in the \
bull case, bear case, and financial summary must be traceable to a specific figure, trend, or \
fact provided here. Do not invent numbers.

=== FINANCIAL METRICS ({period_label}) ===
{metrics_block}

=== YEAR-OVER-YEAR CHANGES ===
{comparison_block}

=== MANAGEMENT TONE ===
{tone_block}

=== RISK FACTOR CHANGES vs PRIOR PERIOD ===
{risk_block}

=== PEER BENCHMARKING ({period_label}) ===
{benchmark_block}

=== BUSINESS DESCRIPTION (from filing) ===
{business_context}

Write a company_overview, financial_summary, bull_case, bear_case, key_risks, and \
questions_to_investigate. Ground every point in the data above.
"""


def _format_metrics(metrics) -> str:
    lines = []
    for field, value in metrics.model_dump().items():
        if value is None or field in ("company", "ticker", "period_label", "period_type", "fiscal_year", "fiscal_quarter", "currency", "unit"):
            continue
        lines.append(f"- {field}: {value}")
    return "\n".join(lines) or "(no data)"


def _format_comparison(comparison) -> str:
    if comparison is None:
        return "(no prior period available)"
    lines = []
    for delta in comparison.deltas:
        if delta.pct_change is None:
            continue
        lines.append(
            f"- {delta.metric}: {delta.prior_value} -> {delta.current_value} "
            f"({delta.pct_change:+.1f}%)"
        )
    return "\n".join(lines) or "(no comparable metrics)"


def _format_tone(tone, tone_comparison) -> str:
    lines = [
        f"- Sentiment: {tone.sentiment} (confidence score {tone.confidence_score:.2f})",
        f"- Summary: {tone.summary}",
    ]
    if tone_comparison is not None:
        lines.append(f"- Shift vs prior period: {tone_comparison.tone_shift} -- {tone_comparison.explanation}")
    return "\n".join(lines)


def _format_risks(risk_comparison) -> str:
    if risk_comparison is None:
        return "(no prior period available)"
    lines = []
    for risk in risk_comparison.new_risks:
        lines.append(f"- NEW: {risk.title} (Category: {risk.category}, Severity: {risk.severity})")
    for risk in risk_comparison.escalated_risks:
        lines.append(f"- ESCALATED: {risk.title} (now Severity: {risk.severity})")
    for risk in risk_comparison.removed_risks:
        lines.append(f"- REMOVED: {risk.title}")
    if not lines:
        lines.append("- No new, escalated, or removed risks vs the prior period.")
    return "\n".join(lines)


def _format_benchmark(benchmark) -> str:
    if benchmark is None or not benchmark.rows:
        return "(no peer data available)"
    lines = []
    for row in benchmark.rows:
        lines.append(
            f"- {row.company} ({row.ticker}): revenue={row.revenue}, "
            f"revenue_growth_yoy_pct={row.revenue_growth_yoy_pct}, "
            f"ebitda_margin_pct={row.ebitda_margin_pct}, "
            f"operating_margin_pct={row.operating_margin_pct}, "
            f"net_margin_pct={row.net_margin_pct}, "
            f"capex_pct_of_revenue={row.capex_pct_of_revenue}, "
            f"debt_to_ebitda={row.debt_to_ebitda}"
        )
    return "\n".join(lines)


def _prior_period_label(period_label: str) -> str | None:
    if period_label.startswith("FY") and period_label[2:].isdigit():
        return f"FY{int(period_label[2:]) - 1}"
    return None


def generate_investment_memo(
    docs: list[ParsedDocument],
    ticker: str,
    period_label: str,
    peer_tickers: list[str] | None = None,
) -> InvestmentMemo:
    """Generate an investment memo for ticker/period_label, grounded in
    extracted metrics, comparisons, tone, risk changes, and peer benchmarks."""
    ref_doc = next(d for d in docs if d.ticker == ticker and d.period_label == period_label)

    metrics = get_metrics(ticker, period_label)
    tone = get_tone(ticker, period_label)

    prior_label = _prior_period_label(period_label)
    comparison = None
    tone_comparison = None
    risk_comparison = None
    if prior_label and get_document(docs, ticker, prior_label) is not None:
        prior_metrics = get_metrics(ticker, prior_label)
        comparison = compute_metric_comparison(metrics, prior_metrics, comparison_type="YoY")

        prior_tone = get_tone(ticker, prior_label)
        tone_comparison = compare_tone(tone, prior_tone)

        current_risks = get_risks(ticker, period_label)
        prior_risks = get_risks(ticker, prior_label)
        risk_comparison = compare_risk_factors(current_risks, prior_risks)

    benchmark = None
    if peer_tickers:
        all_tickers = [ticker] + [t for t in peer_tickers if t != ticker]
        benchmark = build_benchmark_table(docs, all_tickers, period_label, metrics_fn=lambda _docs, t, p: get_metrics(t, p))

    business_context = get_section_text(docs, ticker, period_label, "mda") or ""

    prompt = MEMO_PROMPT.format(
        company=ref_doc.company,
        ticker=ticker,
        period_label=period_label,
        metrics_block=_format_metrics(metrics),
        comparison_block=_format_comparison(comparison),
        tone_block=_format_tone(tone, tone_comparison),
        risk_block=_format_risks(risk_comparison),
        benchmark_block=_format_benchmark(benchmark),
        business_context=business_context[:3000],
    )

    llm = get_llm(temperature=config.LLM_TEMPERATURE_GENERATION)
    extracted = invoke_structured(llm, _ExtractedMemo, prompt)

    return InvestmentMemo(
        company=ref_doc.company,
        ticker=ticker,
        period_label=period_label,
        **extracted.model_dump(),
    )
