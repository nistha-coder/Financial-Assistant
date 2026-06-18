"""Extract structured financial metrics from a parsed filing.

Strategy: the "Financial Statements (Summary)" section of each filing presents
figures as clean "Label: value" lines, which we parse deterministically with
regex for accuracy. Margins are then computed from those figures. Guidance
figures live in a narrative forward-guidance paragraph, so those are extracted
with a small, focused LLM call.
"""
import re
from typing import Optional

from pydantic import BaseModel, Field

from app import config
from app.ingestion.pipeline import get_section_text
from app.llm import get_llm, invoke_structured
from app.models.schemas import FinancialMetrics, ParsedDocument

# Maps the labels used in the "Financial Statements (SUMMARY)" section to
# FinancialMetrics field names.
LABEL_TO_FIELD = {
    "revenue": "revenue",
    "gross profit": "gross_profit",
    "operating income": "operating_income",
    "ebitda": "ebitda",
    "net income": "net_income",
    "operating cash flow": "operating_cash_flow",
    "capital expenditures": "capex",
    "free cash flow": "free_cash_flow",
    "total debt": "total_debt",
    "cash and cash equivalents": "cash_and_equivalents",
}

LINE_RE = re.compile(r"^([A-Za-z][A-Za-z &]+):\s*\$?([\d,]+\.?\d*)\s*$")


def parse_financial_statement_lines(financials_text: str) -> dict[str, float]:
    """Deterministically parse 'Label: 1,234.5' lines into field -> value."""
    values: dict[str, float] = {}
    for line in financials_text.split("\n"):
        match = LINE_RE.match(line.strip())
        if not match:
            continue
        label = match.group(1).strip().lower()
        field = LABEL_TO_FIELD.get(label)
        if field:
            values[field] = float(match.group(2).replace(",", ""))
    return values


def _pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 1)


def compute_margins(values: dict[str, float]) -> dict[str, float]:
    revenue = values.get("revenue")
    margins = {}
    if (gp := _pct(values.get("gross_profit"), revenue)) is not None:
        margins["gross_margin_pct"] = gp
    if (om := _pct(values.get("operating_income"), revenue)) is not None:
        margins["operating_margin_pct"] = om
    if (nm := _pct(values.get("net_income"), revenue)) is not None:
        margins["net_margin_pct"] = nm
    if (em := _pct(values.get("ebitda"), revenue)) is not None:
        margins["ebitda_margin_pct"] = em
    return margins


class _ExtractedGuidance(BaseModel):
    guidance_revenue_low: Optional[float] = Field(default=None, description="Low end of revenue guidance, in millions")
    guidance_revenue_high: Optional[float] = Field(default=None, description="High end of revenue guidance, in millions")
    guidance_eps_low: Optional[float] = Field(default=None, description="Low end of diluted EPS guidance")
    guidance_eps_high: Optional[float] = Field(default=None, description="High end of diluted EPS guidance")
    guidance_notes: Optional[str] = Field(default=None, description="Any qualitative notes/caveats about the guidance")


GUIDANCE_PROMPT = """The text below is the "Forward Guidance" paragraph from {ticker}'s \
{period_label} annual report. It projects figures for the company's NEXT fiscal period \
(whatever year that paragraph names) -- extract those figures regardless of which year \
they refer to. Revenue guidance is given as a range in millions of dollars. EPS guidance \
is given as a range in dollars per share. If a figure is not present, leave it null.

TEXT:
{context}
"""


def extract_guidance(docs: list[ParsedDocument], ticker: str, period_label: str) -> _ExtractedGuidance:
    context = get_section_text(docs, ticker, period_label, "forward_guidance")
    if not context:
        return _ExtractedGuidance()
    llm = get_llm(temperature=config.LLM_TEMPERATURE_EXTRACTION)
    prompt = GUIDANCE_PROMPT.format(ticker=ticker, period_label=period_label, context=context)
    return invoke_structured(llm, _ExtractedGuidance, prompt)


def extract_financial_metrics(docs: list[ParsedDocument], ticker: str, period_label: str) -> FinancialMetrics:
    """Extract a FinancialMetrics record for one company/period from its parsed documents."""
    financials_text = get_section_text(docs, ticker, period_label, "financials")
    if not financials_text:
        raise ValueError(f"No financial statements section found for {ticker} {period_label}")

    values = parse_financial_statement_lines(financials_text)
    values.update(compute_margins(values))
    guidance = extract_guidance(docs, ticker, period_label)

    ref_doc = next(d for d in docs if d.ticker == ticker and d.period_label == period_label)

    return FinancialMetrics(
        company=ref_doc.company,
        ticker=ref_doc.ticker,
        period_label=ref_doc.period_label,
        period_type=ref_doc.period_type,
        fiscal_year=ref_doc.fiscal_year,
        fiscal_quarter=ref_doc.fiscal_quarter,
        **values,
        **guidance.model_dump(),
    )
