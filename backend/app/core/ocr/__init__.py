"""
OCR-provider factory. Select via `settings.OCR_PROVIDER`:
  - "zia" → ZiaOcrProvider (Catalyst Zia OCR — real image/handwriting/PDF OCR,
            up to 20MB, 10 Indian languages) — the only provider now

The local pdfplumber-based provider (digital-PDF text only, no real OCR) was
removed — Zia already covers everything it did and more, and it was the last
thing in this codebase still using pdfplumber for OCR (extractors.py's
PDF extractors were also switched to call this factory instead).
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.ocr.base import OcrProvider

__all__ = ["OcrProvider", "get_ocr_provider"]


@lru_cache(maxsize=1)
def get_ocr_provider() -> OcrProvider:
    provider = getattr(settings, "OCR_PROVIDER", "zia")

    if provider == "zia":
        from app.core.ocr.zia import ZiaOcrProvider

        return ZiaOcrProvider(project_id=settings.CATALYST_PROJECT_ID)

    raise ValueError(f"Unknown OCR_PROVIDER: {provider!r}")
