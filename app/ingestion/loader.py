"""Raw text loaders for PDF and plain-text source documents."""
from pathlib import Path

from pypdf import PdfReader


def load_pdf_text(path: Path) -> str:
    """Extract raw text from a PDF, page by page, joined with newlines."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_document_text(path: Path) -> str:
    """Dispatch to the correct loader based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf_text(path)
    if suffix in (".txt", ".md"):
        return load_text_file(path)
    raise ValueError(f"Unsupported file type: {path.suffix} for {path}")