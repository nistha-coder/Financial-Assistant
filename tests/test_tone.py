"""Validate management tone analysis on planted confident vs cautious passages.

Covers the success metric: "tone analysis must correctly distinguish a
planted cautious passage from a confident one." Requires a live LLM call,
so it's skipped if the free-tier provider is currently rate-limited.
"""
from app.analysis.tone import analyze_tone, compare_tone


def test_tone_distinguishes_confident_vs_cautious(docs, ground_truth, require_llm):
    for ticker, company in ground_truth["companies"].items():
        for period_label, expected in company["periods"].items():
            if "tone" not in expected:
                continue
            tone = analyze_tone(docs, ticker, period_label)
            if expected["tone"] == "confident":
                assert tone.sentiment in ("confident", "neutral")
                assert tone.confidence_score >= 0.5
            elif expected["tone"] == "cautious":
                assert tone.sentiment in ("cautious", "neutral")
                assert tone.confidence_score <= 0.5


def test_tone_shift_flagged_between_periods(docs, ground_truth, require_llm):
    """SOLR shifts from confident (FY2023) to cautious (FY2024) -- the
    comparison must flag this as 'more_cautious'."""
    current = analyze_tone(docs, "SOLR", "FY2024")
    prior = analyze_tone(docs, "SOLR", "FY2023")
    comparison = compare_tone(current, prior)
    assert comparison.tone_shift == "more_cautious"
