"""
Vertex AI (Gemini) client bootstrap — replaces app/core/groq_client.py.

Auth is Application Default Credentials: a service-account JSON pointed to by
GOOGLE_APPLICATION_CREDENTIALS, or the ambient identity when running on GCP
compute. This module's job is to fail fast at startup if the project id is
missing, log the configured models, and provide a shared resilience wrapper so
every LLM call site (conversation_service, investigator_support) degrades the
same way under a transient outage instead of each reinventing retry logic.
"""

import os
from functools import lru_cache
from typing import Awaitable, Callable, TypeVar

import structlog
from google import genai
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

log = structlog.get_logger(__name__)

T = TypeVar("T")


class AiUnavailableError(Exception):
    """Raised when the Gemini call failed after retries — narration is unavailable,
    but deterministic tool output (already computed separately) is still valid."""


def _is_transient(exc: BaseException) -> bool:
    """
    Retry on connection failures / timeouts / 5xx (incl. Gemini's 429 RESOURCE_EXHAUSTED,
    which is transient rate-limiting, not a bad request) — never on another 4xx (bad
    request, bad prompt), which a retry can't fix.
    """
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status_code is not None:
        return status_code >= 500 or status_code == 429
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


def init_vertex_ai() -> None:
    if not settings.VERTEX_PROJECT_ID:
        raise RuntimeError(
            "VERTEX_PROJECT_ID is not set — every conversational/narration feature requires it. "
            "Add it to .env before starting the API."
        )
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        if not os.path.exists(creds_path):
            module_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(module_dir))
            alt_path = os.path.join(backend_dir, "secrets", "gcp-service-account.json")
            if os.path.exists(alt_path):
                creds_path = alt_path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    log.info(
        "Vertex AI client configured",
        project=settings.VERTEX_PROJECT_ID,
        location=settings.VERTEX_LOCATION,
        llm_model=settings.GEMINI_MODEL,
        fast_model=settings.GEMINI_MODEL_FAST,
        live_model=settings.GEMINI_LIVE_MODEL,
        credentials_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    )


@lru_cache(maxsize=1)
def get_genai_client() -> genai.Client:
    """Shared Vertex-AI-backed genai client — one per process, memoized like the
    other provider factories in app/core/{storage,cache,ocr,nlp}."""
    return genai.Client(
        vertexai=True,
        project=settings.VERTEX_PROJECT_ID,
        location=settings.VERTEX_LOCATION,
    )


async def resilient_vertex_call(fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    """
    Wraps a single async Gemini call with bounded retry + backoff.
    Raises AiUnavailableError (never the raw SDK exception) once exhausted, so
    call sites can distinguish "AI unavailable" from "our own bug" cleanly.
    """

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def _call() -> T:
        return await fn(*args, **kwargs)

    try:
        return await _call()
    except Exception as exc:
        log.error("Vertex AI call failed after retries", error=str(exc))
        raise AiUnavailableError(str(exc)) from exc
