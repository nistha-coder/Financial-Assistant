"""Central configuration for the AI Financial Document Analyst."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Silence a known harmless chromadb telemetry error with newer posthog versions.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

BASE_DIR = Path(__file__).resolve().parent.parent

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_LLM_MODEL = os.getenv("OPENROUTER_LLM_MODEL", "nvidia/nemotron-nano-9b-v2:free")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR = str(BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"))
SAMPLE_DATA_DIR = BASE_DIR / os.getenv("SAMPLE_DATA_DIR", "data/sample_filings")

# LLM generation defaults
LLM_TEMPERATURE_EXTRACTION = 0.0  # deterministic for structured extraction
LLM_TEMPERATURE_ANALYSIS = 0.1
LLM_TEMPERATURE_GENERATION = 0.3  # memo generation can be slightly more fluent

# Chunking defaults for the RAG pipeline
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


def require_api_key() -> None:
    """Raise a clear error if the OpenRouter API key is not configured."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your "
            "OpenRouter API key from https://openrouter.ai/keys"
        )