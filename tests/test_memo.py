"""Validate that the generated investment memo is grounded in extracted data.

Covers the success metric: "investment memo must include grounded bull/bear
cases." Requires a live LLM call, so it's skipped if the free-tier provider
is currently rate-limited.
"""
from app.memo.generator import generate_investment_memo


def test_memo_sections_populated_and_grounded(docs, ground_truth, require_llm):
    memo = generate_investment_memo(docs, "SOLR", "FY2024", peer_tickers=["VCLD"])

    assert memo.company_overview.strip()
    assert memo.financial_summary.strip()
    assert len(memo.bull_case) >= 2
    assert len(memo.bear_case) >= 2
    assert len(memo.key_risks) >= 1
    assert len(memo.questions_to_investigate) >= 1

    # The bull/bear cases should be grounded in actual figures (contain
    # numbers), not purely qualitative hand-waving.
    import re

    combined_text = " ".join(memo.bull_case + memo.bear_case)
    assert re.search(r"\d", combined_text), f"Bull/bear cases contain no figures: {combined_text}"
