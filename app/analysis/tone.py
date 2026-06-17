"""Management tone / sentiment analysis over MD&A and earnings call commentary."""
from pydantic import BaseModel, Field

from app import config
from app.ingestion.pipeline import get_section_text
from app.llm import get_llm, invoke_structured
from app.models.schemas import ParsedDocument, SentimentLabel, ToneAnalysis, ToneComparison


class _ExtractedTone(BaseModel):
    sentiment: SentimentLabel = Field(
        description="Overall tone of management commentary: 'confident', 'neutral', or 'cautious'"
    )
    confidence_score: float = Field(
        ge=0, le=1, description="0.0 = very cautious/hedging, 0.5 = neutral, 1.0 = very confident"
    )
    hedging_phrases: list[str] = Field(
        default_factory=list,
        description="Direct quotes showing hedging, uncertainty, or caution (e.g. 'we cannot be certain', 'may', 'could potentially')",
    )
    confidence_phrases: list[str] = Field(
        default_factory=list,
        description="Direct quotes showing confidence or optimism (e.g. 'we are confident', 'robust demand')",
    )
    summary: str = Field(description="2-3 sentence summary of management's tone and outlook")


TONE_PROMPT = """You are an expert financial analyst specialising in linguistic tone analysis \
of management commentary. Analyse the tone of the following management commentary for \
{ticker} ({period_label}).

Look for:
- Confidence/optimism: phrases like "we are confident", "robust", "strong momentum", "no concerns"
- Hedging/caution: phrases like "we cannot be certain", "may", "could potentially", "it's possible", "we believe but", "uncertain"

Classify the overall sentiment, assign a confidence_score from 0 (very cautious) to 1 \
(very confident), and extract direct supporting quotes for both hedging and confidence \
language (empty lists are fine if none are present).

MANAGEMENT COMMENTARY:
{context}
"""


def analyze_tone(docs: list[ParsedDocument], ticker: str, period_label: str) -> ToneAnalysis:
    """Analyse management tone for a company/period using its MD&A and transcript commentary."""
    context = get_section_text(docs, ticker, period_label, "mda")
    if not context:
        raise ValueError(f"No management commentary found for {ticker} {period_label}")

    llm = get_llm(temperature=config.LLM_TEMPERATURE_ANALYSIS)
    prompt = TONE_PROMPT.format(ticker=ticker, period_label=period_label, context=context)
    extracted = invoke_structured(llm, _ExtractedTone, prompt)

    return ToneAnalysis(
        company=ticker,
        period_label=period_label,
        **extracted.model_dump(),
    )


def compare_tone(current: ToneAnalysis, prior: ToneAnalysis) -> ToneComparison:
    """Compare two periods' tone analyses and flag a shift, based on the
    computed confidence_score delta (deterministic threshold)."""
    delta = current.confidence_score - prior.confidence_score
    threshold = 0.1
    if delta <= -threshold:
        shift = "more_cautious"
    elif delta >= threshold:
        shift = "more_confident"
    else:
        shift = "unchanged"

    explanation = (
        f"{current.company}: confidence score moved from {prior.confidence_score:.2f} "
        f"({prior.period_label}, {prior.sentiment}) to {current.confidence_score:.2f} "
        f"({current.period_label}, {current.sentiment}), a change of {delta:+.2f}. "
    )
    if shift == "more_cautious":
        explanation += "Management commentary shows increased hedging language: " + "; ".join(
            current.hedging_phrases[:3]
        )
    elif shift == "more_confident":
        explanation += "Management commentary shows increased confidence language: " + "; ".join(
            current.confidence_phrases[:3]
        )
    else:
        explanation += "Overall tone is broadly unchanged versus the prior period."

    return ToneComparison(
        company=current.company,
        current_period=current.period_label,
        prior_period=prior.period_label,
        current_tone=current,
        prior_tone=prior,
        tone_shift=shift,
        explanation=explanation,
    )
