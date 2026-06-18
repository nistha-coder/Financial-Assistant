"""Validate deterministic YoY metric comparison arithmetic."""
from app.extraction.comparison import compute_metric_comparison
from app.models.schemas import FinancialMetrics


def _metrics(**overrides) -> FinancialMetrics:
    base = dict(
        company="Acme",
        ticker="ACME",
        period_label="FY2024",
        period_type="annual",
        fiscal_year=2024,
        revenue=200.0,
        ebitda=40.0,
    )
    base.update(overrides)
    return FinancialMetrics(**base)


def test_compute_metric_comparison_deltas():
    current = _metrics(revenue=220.0, ebitda=44.0, period_label="FY2024")
    prior = _metrics(revenue=200.0, ebitda=40.0, period_label="FY2023")

    comparison = compute_metric_comparison(current, prior, comparison_type="YoY")

    deltas = {d.metric: d for d in comparison.deltas}
    assert deltas["revenue"].absolute_change == 20.0
    assert deltas["revenue"].pct_change == 10.0
    assert deltas["ebitda"].absolute_change == 4.0
    assert deltas["ebitda"].pct_change == 10.0


def test_compute_metric_comparison_handles_missing_values():
    current = _metrics(revenue=220.0, ebitda=None, period_label="FY2024")
    prior = _metrics(revenue=200.0, ebitda=40.0, period_label="FY2023")

    comparison = compute_metric_comparison(current, prior, comparison_type="YoY")

    deltas = {d.metric: d for d in comparison.deltas}
    assert deltas["ebitda"].current_value is None
    assert deltas["ebitda"].absolute_change is None
    assert deltas["ebitda"].pct_change is None
