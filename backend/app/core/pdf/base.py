"""
Provider-agnostic HTML→PDF renderer.

Reports are built as HTML and rendered to PDF by the configured provider:
  - "local"      → xhtml2pdf, in-process
  - "smartbrowz" → Catalyst SmartBrowz (headless Chromium) — better fidelity

Password protection stays separate (pypdf, at the endpoint), so it applies
identically regardless of renderer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class PdfRenderer(ABC):
    @abstractmethod
    async def render_html(self, html: str, pdf_options: Optional[dict] = None) -> bytes:
        """Render an HTML document to PDF bytes."""
