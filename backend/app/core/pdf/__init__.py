"""
PDF-renderer factory. Select via `settings.PDF_PROVIDER`:
  - "local"      → LocalPdfRenderer (xhtml2pdf) — default
  - "smartbrowz" → SmartBrowzPdfRenderer (Catalyst SmartBrowz)
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.pdf.base import PdfRenderer

__all__ = ["PdfRenderer", "get_pdf_renderer"]


@lru_cache(maxsize=1)
def get_pdf_renderer() -> PdfRenderer:
    provider = getattr(settings, "PDF_PROVIDER", "local")

    if provider == "local":
        from app.core.pdf.local_renderer import LocalPdfRenderer

        return LocalPdfRenderer()

    if provider == "smartbrowz":
        from app.core.pdf.smartbrowz import SmartBrowzPdfRenderer

        return SmartBrowzPdfRenderer(project_id=settings.CATALYST_PROJECT_ID)

    raise ValueError(f"Unknown PDF_PROVIDER: {provider!r}")
