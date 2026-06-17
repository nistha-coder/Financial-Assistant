"""Extract and compare risk factor disclosures across periods.

Each risk factor in our filings is presented in a consistent format:

    1. <Title> (Category: <Category>, Severity: <Severity>)
    <description paragraph>

This is parsed deterministically with regex for accuracy. Comparison across
periods (new / escalated / removed / unchanged risks) is also computed
deterministically by matching risk titles.
"""
import re

from app.ingestion.pipeline import get_section_text
from app.models.schemas import ParsedDocument, RiskComparison, RiskFactor, RiskFactorList, RiskSeverity

HEADER_RE = re.compile(
    r"^\d+\.\s+(?P<title>.+?)\s+\(Category:\s*(?P<category>\w+),\s*Severity:\s*(?P<severity>\w+)\)\s*$",
    re.MULTILINE,
)

SEVERITY_RANK: dict[RiskSeverity, int] = {"low": 1, "medium": 2, "high": 3}


def parse_risk_factors(risk_text: str) -> list[RiskFactor]:
    """Parse numbered risk factor entries out of an Item 1A risk factors section."""
    matches = list(HEADER_RE.finditer(risk_text))
    risks: list[RiskFactor] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(risk_text)
        description = risk_text[start:end].strip()
        risks.append(
            RiskFactor(
                category=match.group("category"),
                title=match.group("title"),
                description=description,
                severity=match.group("severity").lower(),  # type: ignore[arg-type]
            )
        )
    return risks


def extract_risk_factors(docs: list[ParsedDocument], ticker: str, period_label: str) -> RiskFactorList:
    risk_text = get_section_text(docs, ticker, period_label, "risk_factors")
    if not risk_text:
        raise ValueError(f"No risk factors section found for {ticker} {period_label}")

    ref_doc = next(d for d in docs if d.ticker == ticker and d.period_label == period_label)
    return RiskFactorList(
        company=ref_doc.company,
        period_label=period_label,
        risks=parse_risk_factors(risk_text),
    )


def compare_risk_factors(current: RiskFactorList, prior: RiskFactorList) -> RiskComparison:
    """Flag new, escalated, removed, and unchanged risk factors between two periods."""
    current_by_title = {r.title: r for r in current.risks}
    prior_by_title = {r.title: r for r in prior.risks}

    new_risks = [r for title, r in current_by_title.items() if title not in prior_by_title]
    removed_risks = [r for title, r in prior_by_title.items() if title not in current_by_title]

    escalated_risks: list[RiskFactor] = []
    unchanged_titles: list[str] = []
    for title, current_risk in current_by_title.items():
        prior_risk = prior_by_title.get(title)
        if prior_risk is None:
            continue
        if SEVERITY_RANK[current_risk.severity] > SEVERITY_RANK[prior_risk.severity]:
            escalated_risks.append(current_risk)
        else:
            unchanged_titles.append(title)

    return RiskComparison(
        company=current.company,
        current_period=current.period_label,
        prior_period=prior.period_label,
        new_risks=new_risks,
        escalated_risks=escalated_risks,
        removed_risks=removed_risks,
        unchanged_risk_titles=unchanged_titles,
    )
