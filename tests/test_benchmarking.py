"""Validate the cross-company benchmarking table.

Covers the success metric: "competitor benchmarking table must be accurate
for all companies." Margins/growth/leverage are computed deterministically
from FinancialMetrics, so a stubbed metrics_fn (sourced from
ground_truth.json) is enough to validate the arithmetic without any LLM call.
"""
from app.benchmarking.benchmark import build_benchmark_table
from app.models.schemas import FinancialMetrics


def _metrics_from_ground_truth(ground_truth, ticker, period_label) -> FinancialMetrics:
    company = ground_truth["companies"][ticker]
    period = company["periods"][period_label]
    return FinancialMetrics(
        company=company["name"],
        ticker=ticker,
        period_label=period_label,
        period_type="annual",
        fiscal_year=int(period_label[2:]),
        revenue=period["revenue"],
        ebitda=period["ebitda"],
        gross_profit=period["gross_profit"],
        operating_income=period["operating_income"],
        net_income=period["net_income"],
        gross_margin_pct=period["gross_margin_pct"],
        operating_margin_pct=period["operating_margin_pct"],
        net_margin_pct=period["net_margin_pct"],
        ebitda_margin_pct=period["ebitda_margin_pct"],
        operating_cash_flow=period["operating_cash_flow"],
        capex=period["capex"],
        free_cash_flow=period["free_cash_flow"],
        total_debt=period["total_debt"],
        cash_and_equivalents=period["cash_and_equivalents"],
    )


def test_benchmark_table_accuracy(docs, ground_truth):
    def metrics_fn(_docs, ticker, period_label):
        return _metrics_from_ground_truth(ground_truth, ticker, period_label)

    table = build_benchmark_table(docs, ["SOLR", "VCLD"], "FY2024", metrics_fn=metrics_fn)
    rows = {row.ticker: row for row in table.rows}

    assert set(rows.keys()) == {"SOLR", "VCLD"}

    solr_2023 = ground_truth["companies"]["SOLR"]["periods"]["FY2023"]
    solr_2024 = ground_truth["companies"]["SOLR"]["periods"]["FY2024"]
    expected_growth = round((solr_2024["revenue"] - solr_2023["revenue"]) / solr_2023["revenue"] * 100, 1)

    solr_row = rows["SOLR"]
    assert solr_row.revenue == solr_2024["revenue"]
    assert solr_row.revenue_growth_yoy_pct == expected_growth
    assert solr_row.ebitda_margin_pct == solr_2024["ebitda_margin_pct"]
    assert solr_row.operating_margin_pct == solr_2024["operating_margin_pct"]
    assert solr_row.net_margin_pct == solr_2024["net_margin_pct"]
    assert solr_row.capex_pct_of_revenue == round(solr_2024["capex"] / solr_2024["revenue"] * 100, 1)
    assert solr_row.debt_to_ebitda == round(solr_2024["total_debt"] / solr_2024["ebitda"], 2)
