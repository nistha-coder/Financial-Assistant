"""Pydantic schemas shared across the ingestion, RAG, extraction and analysis modules."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

PeriodType = Literal["annual", "quarterly"]
DocType = Literal["10-K", "10-Q", "annual_report", "earnings_call"]
SectionType = Literal["financials", "mda", "risk_factors", "forward_guidance", "transcript_qa", "other"]


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
class DocumentSection(BaseModel):
    section_type: SectionType
    title: str
    content: str


class ParsedDocument(BaseModel):
    company: str
    ticker: str
    period_label: str  # e.g. "FY2023", "Q2 FY2024"
    period_type: PeriodType
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    doc_type: DocType
    source_path: str
    sections: list[DocumentSection]
    raw_text: str


# ---------------------------------------------------------------------------
# Financial metric extraction
# ---------------------------------------------------------------------------
class FinancialMetrics(BaseModel):
    """Structured financial metrics extracted from a single filing/period."""

    company: str
    ticker: str
    period_label: str
    period_type: PeriodType
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    currency: str = Field(default="USD", description="Reporting currency, e.g. USD")
    unit: str = Field(default="millions", description="Unit of the figures, e.g. millions, thousands")

    revenue: Optional[float] = Field(default=None, description="Total revenue / net sales")
    ebitda: Optional[float] = Field(default=None, description="EBITDA")
    gross_profit: Optional[float] = Field(default=None)
    operating_income: Optional[float] = Field(default=None)
    net_income: Optional[float] = Field(default=None)

    gross_margin_pct: Optional[float] = Field(default=None, description="Gross profit / revenue * 100")
    operating_margin_pct: Optional[float] = Field(default=None, description="Operating income / revenue * 100")
    net_margin_pct: Optional[float] = Field(default=None, description="Net income / revenue * 100")
    ebitda_margin_pct: Optional[float] = Field(default=None, description="EBITDA / revenue * 100")

    operating_cash_flow: Optional[float] = Field(default=None)
    free_cash_flow: Optional[float] = Field(default=None)
    capex: Optional[float] = Field(default=None, description="Capital expenditures (positive number)")

    total_debt: Optional[float] = Field(default=None)
    cash_and_equivalents: Optional[float] = Field(default=None)

    guidance_revenue_low: Optional[float] = Field(default=None)
    guidance_revenue_high: Optional[float] = Field(default=None)
    guidance_eps_low: Optional[float] = Field(default=None)
    guidance_eps_high: Optional[float] = Field(default=None)
    guidance_notes: Optional[str] = Field(default=None)


class MetricDelta(BaseModel):
    """Computed change for a single metric between two periods."""

    metric: str
    current_value: Optional[float]
    prior_value: Optional[float]
    absolute_change: Optional[float]
    pct_change: Optional[float]


class MetricComparison(BaseModel):
    company: str
    current_period: str
    prior_period: str
    comparison_type: Literal["YoY", "QoQ"]
    deltas: list[MetricDelta]


# ---------------------------------------------------------------------------
# Management tone analysis
# ---------------------------------------------------------------------------
SentimentLabel = Literal["confident", "neutral", "cautious"]


class ToneAnalysis(BaseModel):
    company: str
    period_label: str
    sentiment: SentimentLabel
    confidence_score: float = Field(ge=0, le=1, description="0 = very cautious, 1 = very confident")
    hedging_phrases: list[str] = Field(default_factory=list)
    confidence_phrases: list[str] = Field(default_factory=list)
    summary: str


class ToneComparison(BaseModel):
    company: str
    current_period: str
    prior_period: str
    current_tone: ToneAnalysis
    prior_tone: ToneAnalysis
    tone_shift: Literal["more_confident", "more_cautious", "unchanged"]
    explanation: str


# ---------------------------------------------------------------------------
# Risk factor extraction
# ---------------------------------------------------------------------------
RiskSeverity = Literal["low", "medium", "high"]


class RiskFactor(BaseModel):
    category: str = Field(description="Short category, e.g. 'Regulatory', 'Supply Chain', 'Competition'")
    title: str
    description: str
    severity: RiskSeverity


class RiskFactorList(BaseModel):
    company: str
    period_label: str
    risks: list[RiskFactor]


class RiskComparison(BaseModel):
    company: str
    current_period: str
    prior_period: str
    new_risks: list[RiskFactor]
    escalated_risks: list[RiskFactor]
    removed_risks: list[RiskFactor]
    unchanged_risk_titles: list[str]


# ---------------------------------------------------------------------------
# Competitor benchmarking
# ---------------------------------------------------------------------------
class BenchmarkRow(BaseModel):
    company: str
    ticker: str
    period_label: str
    revenue: Optional[float]
    revenue_growth_yoy_pct: Optional[float]
    ebitda_margin_pct: Optional[float]
    operating_margin_pct: Optional[float]
    net_margin_pct: Optional[float]
    capex_pct_of_revenue: Optional[float]
    debt_to_ebitda: Optional[float]


class BenchmarkTable(BaseModel):
    period_label: str
    rows: list[BenchmarkRow]


# ---------------------------------------------------------------------------
# Investment memo
# ---------------------------------------------------------------------------
class InvestmentMemo(BaseModel):
    company: str
    ticker: str
    period_label: str
    company_overview: str
    financial_summary: str
    bull_case: list[str]
    bear_case: list[str]
    key_risks: list[str]
    questions_to_investigate: list[str]