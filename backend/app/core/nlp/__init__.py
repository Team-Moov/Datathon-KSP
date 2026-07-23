"""
NER-provider factory. Select via `settings.NLP_PROVIDER`:
  - "zia"    → ZiaNlpProvider (Catalyst Zia text-analytics NER — verified lower
               recall than gemini on Indian-name narrative text)
  - "gemini" → GeminiNlpProvider (Vertex AI, structured JSON extraction) — default

The local spaCy provider was removed along with the spacy/torch/transformers
dependencies it pulled in — Gemini replaced it as the default and nothing else
in this codebase used spaCy.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.nlp.base import NlpProvider

__all__ = ["NlpProvider", "get_nlp_provider"]


@lru_cache(maxsize=1)
def get_nlp_provider() -> NlpProvider:
    provider = getattr(settings, "NLP_PROVIDER", "gemini")

    if provider == "zia":
        from app.core.nlp.zia_nlp import ZiaNlpProvider

        return ZiaNlpProvider(project_id=settings.CATALYST_PROJECT_ID)

    if provider == "gemini":
        from app.core.nlp.gemini_nlp import GeminiNlpProvider

        return GeminiNlpProvider()

    raise ValueError(f"Unknown NLP_PROVIDER: {provider!r}")
