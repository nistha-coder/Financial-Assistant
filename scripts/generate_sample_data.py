#!/usr/bin/env python3
"""Generate realistic sample 10-K filings and earnings call transcripts.

Creates synthetic data for three companies across two fiscal years so that
the full analysis pipeline (metrics extraction, tone analysis, risk factors,
benchmarking, and memo generation) can be exercised end-to-end without real
SEC filings.

Usage:
    python scripts/generate_sample_data.py
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_filings"

# ── Company definitions ──────────────────────────────────────

COMPANIES = [
    {
        "name": "TechVision Inc",
        "ticker": "TVIZ",
        "sector": "Technology / Enterprise Software",
        "years": {
            2023: {
                "revenue": 12450, "gross_profit": 8715, "operating_income": 3735,
                "ebitda": 4355, "net_income": 2988, "operating_cash_flow": 4100,
                "capex": 1200, "free_cash_flow": 2900, "total_debt": 5200,
                "cash": 3800,
                "tone": "confident",
                "risks": [
                    ("Cybersecurity Threats", "Technology", "medium",
                     "The company's cloud platform processes sensitive enterprise data. A significant breach could damage client trust and result in regulatory penalties."),
                    ("Talent Retention", "Operational", "medium",
                     "Competition for skilled AI and cloud engineers remains intense in major technology hubs, putting upward pressure on compensation costs."),
                    ("Macroeconomic Slowdown", "Market", "low",
                     "Enterprise IT spending may be deferred during economic uncertainty, lengthening sales cycles and reducing near-term bookings."),
                    ("Regulatory Compliance", "Regulatory", "low",
                     "Evolving data privacy regulations across jurisdictions increase compliance costs and could restrict product features."),
                ],
                "guidance_rev_low": 14200, "guidance_rev_high": 14800,
                "guidance_eps_low": 3.10, "guidance_eps_high": 3.35,
            },
            2024: {
                "revenue": 14520, "gross_profit": 10308, "operating_income": 4647,
                "ebitda": 5373, "net_income": 3776, "operating_cash_flow": 5050,
                "capex": 1450, "free_cash_flow": 3600, "total_debt": 4800,
                "cash": 5100,
                "tone": "confident",
                "risks": [
                    ("Cybersecurity Threats", "Technology", "high",
                     "Several high-profile industry breaches have heightened scrutiny. The company has increased its security investment but the threat landscape continues to evolve rapidly."),
                    ("AI Regulation", "Regulatory", "medium",
                     "Proposed AI governance frameworks in the EU and US could require significant product modifications and increase compliance overhead."),
                    ("Talent Retention", "Operational", "medium",
                     "Competition for AI/ML talent remains fierce. The company expanded its remote-work programme but attrition in key engineering teams ticked upward."),
                    ("Currency Fluctuations", "Financial", "low",
                     "With 38% of revenue from international markets, unfavourable currency movements could negatively impact reported results."),
                    ("Cloud Concentration Risk", "Technology", "medium",
                     "Heavy reliance on a single major cloud infrastructure provider creates vendor lock-in risk and potential service disruption exposure."),
                ],
                "guidance_rev_low": 16500, "guidance_rev_high": 17200,
                "guidance_eps_low": 3.60, "guidance_eps_high": 3.90,
            },
        },
    },
    {
        "name": "GreenEnergy Corp",
        "ticker": "GNRG",
        "sector": "Renewable Energy / Utilities",
        "years": {
            2023: {
                "revenue": 8900, "gross_profit": 3560, "operating_income": 1780,
                "ebitda": 2670, "net_income": 1246, "operating_cash_flow": 2900,
                "capex": 2100, "free_cash_flow": 800, "total_debt": 12000,
                "cash": 1500,
                "tone": "neutral",
                "risks": [
                    ("Policy and Subsidy Dependence", "Regulatory", "high",
                     "A significant portion of project economics depends on federal renewable energy tax credits. Any reduction or expiration of these incentives would materially impact returns."),
                    ("Supply Chain Disruption", "Operational", "medium",
                     "Solar panel and wind turbine components are sourced from a concentrated set of suppliers, primarily in Asia. Trade restrictions or logistics disruptions could delay project timelines."),
                    ("Interest Rate Sensitivity", "Financial", "high",
                     "The company's capital-intensive business model requires significant project financing. Rising interest rates increase the cost of debt and reduce project IRRs."),
                    ("Weather and Climate Variability", "Operational", "low",
                     "Energy generation volumes are inherently dependent on weather patterns. Unusual weather can cause quarterly generation to deviate from forecasts."),
                ],
                "guidance_rev_low": 10000, "guidance_rev_high": 10800,
                "guidance_eps_low": 1.80, "guidance_eps_high": 2.10,
            },
            2024: {
                "revenue": 10650, "gross_profit": 4473, "operating_income": 2343,
                "ebitda": 3408, "net_income": 1704, "operating_cash_flow": 3600,
                "capex": 2800, "free_cash_flow": 800, "total_debt": 14500,
                "cash": 1800,
                "tone": "cautious",
                "risks": [
                    ("Policy and Subsidy Dependence", "Regulatory", "high",
                     "Legislative proposals to phase down clean energy tax credits create uncertainty around future project economics. Management is actively diversifying revenue streams."),
                    ("Supply Chain Disruption", "Operational", "high",
                     "New tariffs on imported solar components have increased procurement costs by approximately 12%, compressing project margins."),
                    ("Interest Rate Sensitivity", "Financial", "high",
                     "Despite modest rate cuts, borrowing costs remain elevated. The company's leverage ratio has increased to 4.3x net debt/EBITDA."),
                    ("Permitting Delays", "Regulatory", "medium",
                     "Lengthening environmental review timelines at the federal and state level are delaying project commissioning dates by 6-9 months on average."),
                    ("Grid Interconnection Backlogs", "Operational", "medium",
                     "The queue for grid interconnection approval has grown substantially, with average wait times exceeding 3 years in several key markets."),
                ],
                "guidance_rev_low": 11800, "guidance_rev_high": 12500,
                "guidance_eps_low": 2.00, "guidance_eps_high": 2.30,
            },
        },
    },
    {
        "name": "HealthPlus Holdings",
        "ticker": "HLTH",
        "sector": "Healthcare / Pharmaceuticals",
        "years": {
            2023: {
                "revenue": 18200, "gross_profit": 12740, "operating_income": 4550,
                "ebitda": 5460, "net_income": 3276, "operating_cash_flow": 5600,
                "capex": 1800, "free_cash_flow": 3800, "total_debt": 8500,
                "cash": 4200,
                "tone": "confident",
                "risks": [
                    ("Patent Cliff", "Competition", "high",
                     "Key patents on two blockbuster drugs expire within 24 months, exposing approximately $4.2B in annual revenue to generic competition."),
                    ("Regulatory Approval Risk", "Regulatory", "medium",
                     "The late-stage pipeline includes three candidates awaiting FDA decisions. Unfavourable outcomes could significantly reduce the company's growth outlook."),
                    ("Drug Pricing Legislation", "Regulatory", "medium",
                     "Government initiatives to negotiate or cap drug prices could compress margins on the company's highest-revenue products."),
                    ("Clinical Trial Failures", "Operational", "medium",
                     "Phase III clinical trials carry inherent risk of failure. The company currently has $1.8B in capitalised development costs tied to pipeline candidates."),
                ],
                "guidance_rev_low": 19000, "guidance_rev_high": 19800,
                "guidance_eps_low": 4.50, "guidance_eps_high": 4.85,
            },
            2024: {
                "revenue": 19450, "gross_profit": 13420, "operating_income": 4862,
                "ebitda": 5834, "net_income": 3501, "operating_cash_flow": 6100,
                "capex": 2000, "free_cash_flow": 4100, "total_debt": 7800,
                "cash": 5500,
                "tone": "neutral",
                "risks": [
                    ("Patent Cliff", "Competition", "high",
                     "The first of two major patent expirations occurred in Q3. Early generic entry has already eroded unit volumes by 15% for the affected product."),
                    ("Regulatory Approval Risk", "Regulatory", "medium",
                     "Two of three pipeline candidates received FDA approval; the third received a Complete Response Letter requiring additional data, delaying launch by 12-18 months."),
                    ("Drug Pricing Legislation", "Regulatory", "high",
                     "The Inflation Reduction Act's drug price negotiation provisions now cover three of the company's top-10 products, with negotiated prices taking effect next fiscal year."),
                    ("Biosimilar Competition", "Competition", "medium",
                     "Biosimilar versions of a key biologic product have gained 20% market share in the 12 months since launch, with further erosion expected."),
                    ("Supply Chain Quality", "Operational", "low",
                     "An FDA warning letter at a contract manufacturing facility required production transfers, resulting in temporary supply constraints."),
                ],
                "guidance_rev_low": 19800, "guidance_rev_high": 20600,
                "guidance_eps_low": 4.60, "guidance_eps_high": 5.00,
            },
        },
    },
]

# ── MDA templates keyed by tone ──────────────────────────────

MDA_TEMPLATES = {
    "confident": textwrap.dedent("""\
        ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

        Fiscal year {year} was a year of strong execution for {name}. Revenue grew {rev_growth:.1f}% year-over-year to ${revenue:,} million, driven by robust demand across our {sector} portfolio. We are confident that our strategic investments in innovation and market expansion are delivering sustainable competitive advantages.

        Gross margin improved to {gm:.1f}%, reflecting operational efficiencies and a favourable product mix shift toward higher-margin offerings. Operating income reached ${operating_income:,} million, representing an operating margin of {om:.1f}%. We are pleased with these results and believe they demonstrate the scalability of our business model.

        Our balance sheet remains strong with ${cash:,} million in cash and cash equivalents against ${total_debt:,} million in total debt. Free cash flow generation of ${free_cash_flow:,} million underscores our ability to self-fund growth initiatives while returning capital to shareholders.

        Looking ahead, we see no significant concerns that would impede our growth trajectory. Customer engagement metrics are at all-time highs, our pipeline is robust, and we are well-positioned to capture incremental market share.

        Forward Guidance
        For fiscal year {next_year}, management projects revenue in the range of ${guidance_rev_low:,} million to ${guidance_rev_high:,} million. Diluted earnings per share are expected to be between ${guidance_eps_low:.2f} and ${guidance_eps_high:.2f}. This outlook reflects continued strong demand and disciplined cost management.\n"""),

    "neutral": textwrap.dedent("""\
        ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

        {name} delivered steady results in fiscal year {year}. Revenue increased {rev_growth:.1f}% to ${revenue:,} million. While we are encouraged by the progress in several key areas, we acknowledge that the operating environment presents both opportunities and challenges.

        Gross margin was {gm:.1f}%, and operating margin stood at {om:.1f}%. We believe these results are satisfactory given the current market conditions, though we continue to monitor cost pressures that may limit near-term margin expansion.

        Cash and equivalents totalled ${cash:,} million. Total debt stood at ${total_debt:,} million. Free cash flow was ${free_cash_flow:,} million. We are managing our capital structure carefully to balance growth investment with financial flexibility.

        We remain cautiously optimistic about the year ahead. It's possible that certain macro headwinds could impact our results, but we believe our diversified portfolio positions us reasonably well.

        Forward Guidance
        For fiscal year {next_year}, the company expects revenue between ${guidance_rev_low:,} million and ${guidance_rev_high:,} million. Diluted EPS is anticipated in the range of ${guidance_eps_low:.2f} to ${guidance_eps_high:.2f}, subject to market conditions and regulatory developments.\n"""),

    "cautious": textwrap.dedent("""\
        ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

        Fiscal year {year} presented a mixed operating environment for {name}. Revenue grew {rev_growth:.1f}% to ${revenue:,} million, though the pace of growth decelerated relative to the prior year. We cannot be certain that current growth rates will be sustained given the headwinds we are facing.

        Gross margin of {gm:.1f}% and operating margin of {om:.1f}% reflect cost pressures that may persist. While we are taking steps to improve efficiency, we believe it is prudent to set measured expectations. It's possible that margins could come under further pressure if input costs remain elevated.

        Our financial position shows ${cash:,} million in cash against ${total_debt:,} million in total debt. While liquidity remains adequate, our leverage ratio warrants careful monitoring. We are evaluating options to strengthen the balance sheet, though we cannot guarantee the timing or terms of any potential actions.

        We approach the coming year with cautious optimism. The market environment remains uncertain, and we may face headwinds that could potentially affect our ability to meet initial targets.

        Forward Guidance
        For fiscal year {next_year}, management currently estimates revenue in the range of ${guidance_rev_low:,} million to ${guidance_rev_high:,} million. Diluted EPS is expected between ${guidance_eps_low:.2f} and ${guidance_eps_high:.2f}. These projections are subject to significant uncertainty and may be revised as conditions evolve.\n"""),
}

# ── Generators ───────────────────────────────────────────────

def _risk_section(risks: list) -> str:
    lines = ["ITEM 1A. RISK FACTORS\n"]
    for i, (title, cat, sev, desc) in enumerate(risks, 1):
        lines.append(f"{i}. {title} (Category: {cat}, Severity: {sev})")
        lines.append(desc)
        lines.append("")
    return "\n".join(lines)


def _financials_section(d: dict) -> str:
    return textwrap.dedent(f"""\
        ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA

        Financial Statements (Summary)

        Revenue: {d['revenue']:,}
        Gross Profit: {d['gross_profit']:,}
        Operating Income: {d['operating_income']:,}
        EBITDA: {d['ebitda']:,}
        Net Income: {d['net_income']:,}
        Operating Cash Flow: {d['operating_cash_flow']:,}
        Capital Expenditures: {d['capex']:,}
        Free Cash Flow: {d['free_cash_flow']:,}
        Total Debt: {d['total_debt']:,}
        Cash and Cash Equivalents: {d['cash']:,}

        All figures in millions of USD. Fiscal year ended December 31, {d['year']}.
    """)


def _business_section(company: dict) -> str:
    return textwrap.dedent(f"""\
        ITEM 1. BUSINESS

        {company['name']} operates in the {company['sector']} industry. The company
        provides products and services to customers globally, leveraging proprietary
        technology and deep domain expertise to deliver differentiated value.
    """)


def generate_10k(company: dict, year: int, prior_revenue: float | None) -> str:
    d = company["years"][year]
    rev_growth = ((d["revenue"] - prior_revenue) / prior_revenue * 100) if prior_revenue else 0.0
    gm = d["gross_profit"] / d["revenue"] * 100
    om = d["operating_income"] / d["revenue"] * 100

    header = f"{company['name']} ({company['ticker']})\n\n"
    business = _business_section(company)
    risks = _risk_section(d["risks"])
    mda = MDA_TEMPLATES[d["tone"]].format(
        name=company["name"], year=year, revenue=d["revenue"],
        rev_growth=rev_growth, sector=company["sector"],
        operating_income=d["operating_income"], gm=gm, om=om,
        cash=d["cash"], total_debt=d["total_debt"],
        free_cash_flow=d["free_cash_flow"],
        next_year=year + 1,
        guidance_rev_low=d["guidance_rev_low"], guidance_rev_high=d["guidance_rev_high"],
        guidance_eps_low=d["guidance_eps_low"], guidance_eps_high=d["guidance_eps_high"],
    )
    financials = _financials_section({**d, "year": year})

    return header + business + "\n" + risks + "\n" + mda + "\n" + financials


def generate_earnings_call(company: dict, year: int) -> str:
    d = company["years"][year]
    tone = d["tone"]
    name = company["name"]
    ticker = company["ticker"]

    if tone == "confident":
        remarks = (
            f"Thank you for joining {name}'s FY{year} earnings call. We are delighted to "
            f"report another outstanding quarter that caps a strong fiscal year. Revenue of "
            f"${d['revenue']:,} million exceeded the high end of our guidance, and we are confident "
            f"that our strategic positioning will continue to drive robust growth. Our team has "
            f"executed exceptionally well, and we see strong momentum heading into FY{year+1}."
        )
        qa = (
            f"Q: Can you elaborate on your confidence in the FY{year+1} outlook?\n"
            f"A: Absolutely. Our pipeline is the strongest it has been in years. Customer "
            f"retention rates are above 95%, and we are seeing strong demand signals across "
            f"all segments. We have no significant concerns about achieving our targets."
        )
    elif tone == "cautious":
        remarks = (
            f"Good morning and thank you for joining {name}'s FY{year} earnings call. "
            f"Revenue for the year came in at ${d['revenue']:,} million, which was within our "
            f"guidance range. While we are encouraged by certain aspects of our performance, "
            f"we cannot be certain that current trends will persist. The operating environment "
            f"remains challenging, and we may face additional headwinds. We believe it is "
            f"prudent to maintain a measured outlook as we navigate these uncertainties."
        )
        qa = (
            f"Q: How should investors think about the margin trajectory?\n"
            f"A: That is a fair question. We are taking proactive steps to manage costs, but "
            f"it's possible that margins could come under further pressure. We are not in a "
            f"position to guarantee margin expansion in the near term, though we are cautiously "
            f"optimistic that our efficiency initiatives will yield results over time."
        )
    else:
        remarks = (
            f"Thank you for joining us for {name}'s FY{year} results. We delivered revenue of "
            f"${d['revenue']:,} million, consistent with our expectations. Our performance was "
            f"satisfactory, and we believe our strategic initiatives are progressing well. We "
            f"remain focused on executing our plan while adapting to evolving market conditions."
        )
        qa = (
            f"Q: What are the key priorities for FY{year+1}?\n"
            f"A: Our priorities remain consistent — invest in our core capabilities, manage "
            f"costs prudently, and pursue selective growth opportunities. We believe this "
            f"balanced approach positions us reasonably well for the year ahead."
        )

    return (
        f"{name} ({ticker})\n\n"
        f"PREPARED REMARKS — {ticker} FY{year} Earnings Call\n\n"
        f"{remarks}\n\n"
        f"QUESTION AND ANSWER SESSION\n\n"
        f"{qa}\n"
    )


def generate_ground_truth() -> dict:
    """Produce a ground-truth JSON used by the test suite to validate extraction."""
    gt: dict = {}
    for company in COMPANIES:
        ticker = company["ticker"]
        for year, d in company["years"].items():
            period = f"FY{year}"
            gm = round(d["gross_profit"] / d["revenue"] * 100, 1)
            om = round(d["operating_income"] / d["revenue"] * 100, 1)
            nm = round(d["net_income"] / d["revenue"] * 100, 1)
            em = round(d["ebitda"] / d["revenue"] * 100, 1)
            gt[f"{ticker}_{period}"] = {
                "company": company["name"],
                "ticker": ticker,
                "period_label": period,
                "revenue": d["revenue"],
                "gross_profit": d["gross_profit"],
                "operating_income": d["operating_income"],
                "ebitda": d["ebitda"],
                "net_income": d["net_income"],
                "gross_margin_pct": gm,
                "operating_margin_pct": om,
                "net_margin_pct": nm,
                "ebitda_margin_pct": em,
                "operating_cash_flow": d["operating_cash_flow"],
                "free_cash_flow": d["free_cash_flow"],
                "capex": d["capex"],
                "total_debt": d["total_debt"],
                "cash_and_equivalents": d["cash"],
                "risk_count": len(d["risks"]),
                "tone": d["tone"],
            }
    return gt


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating sample filings in {OUTPUT_DIR} …\n")

    for company in COMPANIES:
        ticker = company["ticker"]
        years = sorted(company["years"].keys())

        for i, year in enumerate(years):
            prior_revenue = company["years"][years[i - 1]]["revenue"] if i > 0 else None

            # 10-K filing
            tenk_path = OUTPUT_DIR / f"{ticker}_FY{year}_10K.txt"
            tenk_path.write_text(generate_10k(company, year, prior_revenue), encoding="utf-8")
            print(f"  ✓ {tenk_path.name}")

            # Earnings call transcript
            ec_path = OUTPUT_DIR / f"{ticker}_FY{year}_earnings_call.txt"
            ec_path.write_text(generate_earnings_call(company, year), encoding="utf-8")
            print(f"  ✓ {ec_path.name}")

    # Ground truth
    gt_path = OUTPUT_DIR / "ground_truth.json"
    gt_path.write_text(json.dumps(generate_ground_truth(), indent=2), encoding="utf-8")
    print(f"\n  ✓ {gt_path.name}")

    total = len(COMPANIES) * len(years) * 2
    print(f"\nDone — {total} filing files + ground truth generated.")


if __name__ == "__main__":
    main()
