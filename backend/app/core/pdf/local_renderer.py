"""Local HTML→PDF renderer using xhtml2pdf (in-process, no external service)."""

from __future__ import annotations

import asyncio
import io
from typing import Optional

from app.core.pdf.base import PdfRenderer


class LocalPdfRenderer(PdfRenderer):
    async def render_html(self, html: str, pdf_options: Optional[dict] = None) -> bytes:
        return await asyncio.to_thread(self._render, html)

    @staticmethod
    def _render(html: str) -> bytes:
        # Imported lazily so the dependency is only needed when this provider is used.
        from xhtml2pdf import pisa

        buf = io.BytesIO()
        result = pisa.CreatePDF(src=html, dest=buf)
        if result.err:
            raise RuntimeError(f"xhtml2pdf failed with {result.err} error(s)")
        return buf.getvalue()
