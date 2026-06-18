"""Validate risk factor extraction and period-over-period comparison.

Covers the success metric: "risk comparison must correctly flag a new risk
added in year 2 vs year 1." Both extraction and comparison are deterministic
(regex + title matching), so this test always runs.
"""
from app.extraction.risks import compare_risk_factors, extract_risk_factors


def test_risk_extraction_matches_ground_truth(docs, ground_truth):
    for ticker, company in ground_truth["companies"].items():
        for period_label, expected in company["periods"].items():
            extracted = extract_risk_factors(docs, ticker, period_label)
            expected_risks = {r["title"]: r["severity"] for r in expected["risks"]}
            actual_risks = {r.title: r.severity for r in extracted.risks}
            assert actual_risks == expected_risks, f"{ticker} {period_label}: {actual_risks} != {expected_risks}"


def test_risk_comparison_flags_new_and_escalated(docs, ground_truth):
    for ticker, company in ground_truth["companies"].items():
        periods = company["periods"]
        for period_label, expected in periods.items():
            if "new_risk_titles" not in expected:
                continue
            prior_label = f"FY{int(period_label[2:]) - 1}"
            assert prior_label in periods

            current = extract_risk_factors(docs, ticker, period_label)
            prior = extract_risk_factors(docs, ticker, prior_label)
            comparison = compare_risk_factors(current, prior)

            new_titles = {r.title for r in comparison.new_risks}
            escalated_titles = {r.title for r in comparison.escalated_risks}

            assert new_titles == set(expected["new_risk_titles"]), (
                f"{ticker} {period_label}: new risks {new_titles} != {expected['new_risk_titles']}"
            )
            assert escalated_titles == set(expected["escalated_risk_titles"]), (
                f"{ticker} {period_label}: escalated risks {escalated_titles} != {expected['escalated_risk_titles']}"
            )
