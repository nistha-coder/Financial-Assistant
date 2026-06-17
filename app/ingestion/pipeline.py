"""Discover and parse all source documents under a directory tree."""
from pathlib import Path

from app.ingestion.parser import parse_document
from app.models.schemas import ParsedDocument

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}


def discover_documents(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)


def load_all_documents(root: Path) -> list[ParsedDocument]:
    return [parse_document(p) for p in discover_documents(root)]


def get_document(docs: list[ParsedDocument], ticker: str, period_label: str) -> ParsedDocument | None:
    """Find the parsed document for a given ticker/period, preferring the 10-K."""
    candidates = [d for d in docs if d.ticker == ticker and d.period_label == period_label]
    if not candidates:
        return None
    candidates.sort(key=lambda d: 0 if d.doc_type == "10-K" else 1)
    return candidates[0]


def get_section_text(docs: list[ParsedDocument], ticker: str, period_label: str, section_type: str) -> str | None:
    """Concatenate all section contents of a given type across every document
    for a ticker/period (e.g. MD&A appears in both the 10-K and the transcript)."""
    parts = []
    for doc in docs:
        if doc.ticker != ticker or doc.period_label != period_label:
            continue
        for section in doc.sections:
            if section.section_type == section_type:
                parts.append(section.content)
    return "\n\n".join(parts) if parts else None