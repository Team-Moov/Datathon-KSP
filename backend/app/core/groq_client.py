"""
Groq client bootstrap — replaces app/core/vertex_ai.py.
Groq's API is a plain bearer-token REST call, so there's no SDK-wide init() step
the way Vertex AI needed; this module's job is to fail fast at startup if the key
is missing, log the configured models, and provide a shared resilience wrapper so
every LLM call site (conversation_service, investigator_support) degrades the same
way under a transient outage instead of each reinventing retry logic.
"""

from typing import Awaitable, Callable, TypeVar

import structlog
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
    """Raised when the Groq call failed after retries — narration is unavailable,
    but deterministic tool output (already computed separately) is still valid."""


def _is_transient(exc: BaseException) -> bool:
    """
    Retry on connection failures / timeouts / 5xx — never on a 4xx (bad request,
    bad prompt), which a retry can't fix.
    """
    status_code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if status_code is not None:
        return status_code >= 500
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


def init_groq() -> None:
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set — every conversational/narration feature requires it. "
            "Add it to .env before starting the API."
        )
    log.info(
        "Groq client configured",
        llm_model=settings.GROQ_LLM_MODEL,
        fast_model=settings.GROQ_LLM_MODEL_FAST,
        whisper_model=settings.GROQ_WHISPER_MODEL,
    )


async def resilient_groq_call(fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    """
    Wraps a single async Groq/LangChain call with bounded retry + backoff.
    Raises AiUnavailableError (never the raw Groq exception) once exhausted, so
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
        log.error("Groq call failed after retries", error=str(exc))
        raise AiUnavailableError(str(exc)) from exc
