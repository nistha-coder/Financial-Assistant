"""Compute period-over-period (YoY/QoQ) comparisons between two FinancialMetrics.

Deltas are computed deterministically in Python rather than via the LLM, since
arithmetic on already-extracted figures should be exact.
"""
from typing import Literal

from app.models.schemas import FinancialMetrics, MetricComparison, MetricDelta

COMPARISON_FIELDS = [
    "revenue",
    "ebitda",
    "gross_profit",
    "operating_income",
    "net_income",
    "gross_margin_pct",
    "operating_margin_pct",
    "net_margin_pct",
    "ebitda_margin_pct",
    "operating_cash_flow",
    "free_cash_flow",
    "capex",
    "total_debt",
    "cash_and_equivalents",
]


def _round(value: float | None, ndigits: int = 2) -> float | None:
    return round(value, ndigits) if value is not None else None


def compute_metric_comparison(
    current: FinancialMetrics,
    prior: FinancialMetrics,
    comparison_type: Literal["YoY", "QoQ"],
) -> MetricComparison:
    """Build a MetricComparison with absolute and percentage deltas for each metric."""
    deltas: list[MetricDelta] = []
    for field in COMPARISON_FIELDS:
        current_value = getattr(current, field)
        prior_value = getattr(prior, field)

        absolute_change = None
        pct_change = None
        if current_value is not None and prior_value is not None:
            absolute_change = current_value - prior_value
            if prior_value != 0:
                pct_change = (absolute_change / abs(prior_value)) * 100

        deltas.append(
            MetricDelta(
                metric=field,
                current_value=_round(current_value),
                prior_value=_round(prior_value),
                absolute_change=_round(absolute_change),
                pct_change=_round(pct_change),
            )
        )

    return MetricComparison(
        company=current.company,
        current_period=current.period_label,
        prior_period=prior.period_label,
        comparison_type=comparison_type,
        deltas=deltas,
    )
