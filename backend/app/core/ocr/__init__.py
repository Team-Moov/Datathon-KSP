"""
OCR-provider factory. Select via `settings.OCR_PROVIDER`:
  - "local" → LocalOcrProvider (digital-PDF text only) — default
  - "zia"   → ZiaOcrProvider (Catalyst Zia OCR — real image/handwriting OCR)
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.ocr.base import OcrProvider

__all__ = ["OcrProvider", "get_ocr_provider"]


@lru_cache(maxsize=1)
def get_ocr_provider() -> OcrProvider:
    provider = getattr(settings, "OCR_PROVIDER", "local")

    if provider == "local":
        from app.core.ocr.local_ocr import LocalOcrProvider

        return LocalOcrProvider()

    if provider == "zia":
        from app.core.ocr.zia import ZiaOcrProvider

        return ZiaOcrProvider(project_id=settings.CATALYST_PROJECT_ID)

    raise ValueError(f"Unknown OCR_PROVIDER: {provider!r}")
