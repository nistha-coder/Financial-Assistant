"""Parse raw document text into structured ParsedDocument objects.

Section splitting is regex-based against the standard 10-K "ITEM N." headings
and the "PREPARED REMARKS" / "QUESTION AND ANSWER SESSION" headings used in
earnings call transcripts. This keeps section assignment deterministic and
accurate, which matters for downstream extraction quality.
"""
import re
from pathlib import Path

from app.ingestion.loader import load_document_text
from app.models.schemas import DocumentSection, ParsedDocument, SectionType

# Filename convention: {TICKER}_FY{YEAR}_{10K|earnings_call}.{pdf|txt}
FILENAME_RE = re.compile(r"^(?P<ticker>[A-Z0-9]+)_FY(?P<year>\d{4})_(?P<doctype>10K|earnings_call)$")

# (regex matching the start of a section header line, section_type, title)
SECTION_HEADERS: list[tuple[re.Pattern, SectionType, str]] = [
    (re.compile(r"^ITEM\s+1A\.\s+RISK FACTORS", re.MULTILINE), "risk_factors", "Risk Factors"),
    (re.compile(r"^ITEM\s+7\.\s+MANAGEMENT'S DISCUSSION.*", re.MULTILINE), "mda", "MD&A"),
    (re.compile(r"^ITEM\s+8\.\s+FINANCIAL STATEMENTS.*", re.MULTILINE), "financials", "Financial Statements"),
    (re.compile(r"^ITEM\s+1\.\s+BUSINESS", re.MULTILINE), "other", "Business Overview"),
    (re.compile(r"^PREPARED REMARKS.*", re.MULTILINE), "mda", "Prepared Remarks"),
    (re.compile(r"^QUESTION AND ANSWER SESSION", re.MULTILINE), "transcript_qa", "Q&A"),
]

FORWARD_GUIDANCE_RE = re.compile(r"^Forward Guidance\s*$", re.MULTILINE)


def parse_filename(path: Path) -> dict:
    match = FILENAME_RE.match(path.stem)
    if not match:
        raise ValueError(f"Filename does not match expected convention: {path.name}")
    doctype_raw = match.group("doctype")
    doc_type = "10-K" if doctype_raw == "10K" else "earnings_call"
    return {
        "ticker": match.group("ticker"),
        "fiscal_year": int(match.group("year")),
        "period_label": f"FY{match.group('year')}",
        "period_type": "annual",
        "doc_type": doc_type,
    }


def extract_company_name(text: str) -> str:
    """The first non-empty line is the company name, optionally followed by '(TICKER)'."""
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return re.sub(r"\s*\([A-Z0-9]+\)\s*$", "", line)
    return "Unknown Company"


def split_into_sections(text: str) -> list[DocumentSection]:
    """Split document text into sections using known header patterns.

    Any text before the first recognised header is dropped (title/ticker
    boilerplate). The MD&A section is further split so that the trailing
    "Forward Guidance" paragraph becomes its own `forward_guidance` section.
    """
    matches = []
    for pattern, section_type, title in SECTION_HEADERS:
        m = pattern.search(text)
        if m:
            matches.append((m.start(), section_type, title))
    matches.sort(key=lambda x: x[0])

    sections: list[DocumentSection] = []
    for i, (start, section_type, title) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if section_type == "mda":
            mda_content, guidance_content = _split_forward_guidance(content)
            sections.append(DocumentSection(section_type="mda", title=title, content=mda_content))
            if guidance_content:
                sections.append(
                    DocumentSection(section_type="forward_guidance", title="Forward Guidance", content=guidance_content)
                )
        else:
            sections.append(DocumentSection(section_type=section_type, title=title, content=content))

    if not sections:
        sections.append(DocumentSection(section_type="other", title="Full Document", content=text.strip()))

    return sections


def _split_forward_guidance(mda_content: str) -> tuple[str, str | None]:
    m = FORWARD_GUIDANCE_RE.search(mda_content)
    if not m:
        return mda_content, None
    mda_part = mda_content[: m.start()].strip()
    guidance_part = mda_content[m.start():].strip()
    return mda_part, guidance_part


def parse_document(path: Path) -> ParsedDocument:
    meta = parse_filename(path)
    raw_text = load_document_text(path)
    company = extract_company_name(raw_text)
    sections = split_into_sections(raw_text)

    return ParsedDocument(
        company=company,
        ticker=meta["ticker"],
        period_label=meta["period_label"],
        period_type=meta["period_type"],
        fiscal_year=meta["fiscal_year"],
        fiscal_quarter=None,
        doc_type=meta["doc_type"],
        source_path=str(path),
        sections=sections,
        raw_text=raw_text,
    )