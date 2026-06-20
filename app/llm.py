"""Shared LLM and embedding model factories.

Chat completions go through OpenRouter (OpenAI-compatible API) so we can use
free-tier models. Embeddings run locally via sentence-transformers so the RAG
pipeline has no dependency on embedding API quota.
"""
import time
from functools import lru_cache
from typing import Any, TypeVar

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app import config

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=4)
def get_llm(temperature: float = config.LLM_TEMPERATURE_EXTRACTION) -> ChatOpenAI:
    """Return a cached OpenRouter chat model instance for the given temperature."""
    config.require_api_key()
    return ChatOpenAI(
        model=config.OPENROUTER_LLM_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        temperature=temperature,
        max_retries=6,
        timeout=120,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return a cached local sentence-transformers embedding model."""
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)

def invoke_structured(llm: ChatOpenAI, schema: type[T], prompt: str, retries: int = 5) -> T:
    """Invoke an LLM with a structured-output schema, retrying on transient
    provider errors (common with free-tier OpenRouter models)."""
    structured_llm = llm.with_structured_output(schema)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            result: Any = structured_llm.invoke(prompt)
            return result
        except Exception as exc:  # noqa: BLE001 - retry on any provider error
            last_error = exc
            if attempt < retries - 1:
                time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"LLM structured call failed after {retries} attempts: {last_error}") from last_error