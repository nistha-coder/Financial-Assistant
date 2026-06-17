import json

import pytest

from app import config
from app.ingestion.pipeline import load_all_documents
from app.llm import get_llm


@pytest.fixture(scope="session")
def docs():
    return load_all_documents(config.SAMPLE_DATA_DIR)


@pytest.fixture(scope="session")
def ground_truth():
    with open(config.SAMPLE_DATA_DIR / "ground_truth.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def llm_available():
    """Probe whether the configured LLM provider is currently reachable
    (free-tier OpenRouter models can be daily-rate-limited)."""
    if not config.OPENROUTER_API_KEY:
        return False
    try:
        get_llm(temperature=0.0).invoke("Reply with the single word: ok")
        return True
    except Exception:
        return False


@pytest.fixture
def require_llm(llm_available):
    if not llm_available:
        pytest.skip("LLM provider unavailable (likely free-tier rate limit) -- skipping LLM-dependent test")