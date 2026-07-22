"""
NER-provider factory. Select via `settings.NLP_PROVIDER`:
  - "local" → LocalNlpProvider (spaCy) — default
  - "zia"   → ZiaNlpProvider (Catalyst Zia text-analytics NER)
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.nlp.base import NlpProvider

__all__ = ["NlpProvider", "get_nlp_provider"]


@lru_cache(maxsize=1)
def get_nlp_provider() -> NlpProvider:
    provider = getattr(settings, "NLP_PROVIDER", "local")

    if provider == "local":
        from app.core.nlp.local_nlp import LocalNlpProvider

        return LocalNlpProvider()

    if provider == "zia":
        from app.core.nlp.zia_nlp import ZiaNlpProvider

        return ZiaNlpProvider(project_id=settings.CATALYST_PROJECT_ID)

    raise ValueError(f"Unknown NLP_PROVIDER: {provider!r}")
