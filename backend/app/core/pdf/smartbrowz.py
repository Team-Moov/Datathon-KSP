"""
Catalyst SmartBrowz HTML→PDF renderer (REST-based, shared Catalyst OAuth).

SmartBrowz renders with a real headless Chromium, so CSS/layout fidelity is far
better than an in-process converter. Scope: ZohoCatalyst.pdfshot.execute.

The exact request schema is confirmed on the first live call (docs are gated);
SMARTBROWZ_PDF_URL / the body shape are single config knobs for that.
"""

from __future__ import annotations

from typing import Optional

import httpx
import structlog

from app.core.catalyst_auth import catalyst_auth_header
from app.core.config import settings

from app.core.pdf.base import PdfRenderer

log = structlog.get_logger(__name__)


class SmartBrowzPdfRenderer(PdfRenderer):
    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise RuntimeError("CATALYST_PROJECT_ID is required for SmartBrowz")
        dc = getattr(settings, "CATALYST_DC", "in")
        api_base = getattr(settings, "CATALYST_API_BASE", "") or f"https://api.catalyst.zoho.{dc}"
        # Verified from the zcatalyst-sdk source: SmartBrowz convert_to_pdf() posts to
        # the BROWSER360 service /convert with output_options.output_type = "pdf".
        self.endpoint = (
            getattr(settings, "SMARTBROWZ_PDF_URL", "")
            or f"{api_base}/browser360/v1/project/{project_id}/convert"
        )

    async def render_html(self, html: str, pdf_options: Optional[dict] = None) -> bytes:
        body = {
            "output_options": {"output_type": "pdf"},
            "html": html,
            "pdf_options": {"format": "A4", "print_background": True, **(pdf_options or {})},
        }
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(self.endpoint, json=body, headers=await catalyst_auth_header())
            resp.raise_for_status()
            log.info("SmartBrowz PDF rendered", bytes=len(resp.content))
            return resp.content
