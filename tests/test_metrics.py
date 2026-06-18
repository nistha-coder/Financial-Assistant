"""Validate financial metric extraction against ground_truth.json.

Covers the success metric: "metric extraction must correctly identify all
named financial figures." The figures themselves come from the deterministic
regex parser (`parse_financial_statement_lines` + `compute_margins`), which
requires no LLM call, so this test always runs.
"""
from app.extraction.metrics import compute_margins, parse_financial_statement_lines
from app.ingestion.pipeline import get_section_text

# Fields covered by the deterministic regex parser + computed margins.
DETERMINISTIC_FIELDS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "ebitda",
    "net_income",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "total_debt",
    "cash_and_equivalents",
    "gross_margin_pct",
    "operating_margin_pct",
    "net_margin_pct",
    "ebitda_margin_pct",
]


def test_deterministic_fields_match_ground_truth(docs, ground_truth):
    total = 0
    correct = 0
    mismatches = []

    for ticker, company in ground_truth["companies"].items():
        for period_label, expected in company["periods"].items():
            financials_text = get_section_text(docs, ticker, period_label, "financials")
            assert financials_text, f"No financials section for {ticker} {period_label}"

            values = parse_financial_statement_lines(financials_text)
            values.update(compute_margins(values))

            for field in DETERMINISTIC_FIELDS:
                if field not in expected:
                    continue
                total += 1
                actual = values.get(field)
                expected_value = expected[field]
                if actual is not None and abs(actual - expected_value) < 0.05:
                    correct += 1
                else:
                    mismatches.append((ticker, period_label, field, actual, expected_value))

    accuracy = correct / total
    assert accuracy >= 0.95, f"Accuracy {accuracy:.2%} below 95% threshold. Mismatches: {mismatches}"
    assert not mismatches, f"Mismatches found: {mismatches}"


def test_guidance_extraction(docs, ground_truth, require_llm):
    """Forward-guidance figures are extracted via a small LLM call (Task 5)."""
    from app.extraction.metrics import extract_guidance

    total = 0
    correct = 0
    mismatches = []

    for ticker, company in ground_truth["companies"].items():
        for period_label, expected in company["periods"].items():
            guidance = extract_guidance(docs, ticker, period_label)
            for field in ("guidance_revenue_low", "guidance_revenue_high", "guidance_eps_low", "guidance_eps_high"):
                if field not in expected:
                    continue
                total += 1
                actual = getattr(guidance, field)
                expected_value = expected[field]
                if actual is not None and abs(actual - expected_value) < 0.05:
                    correct += 1
                else:
                    mismatches.append((ticker, period_label, field, actual, expected_value))

    accuracy = correct / total
    assert accuracy >= 0.9, f"Guidance accuracy {accuracy:.2%} below 90% threshold. Mismatches: {mismatches}"
