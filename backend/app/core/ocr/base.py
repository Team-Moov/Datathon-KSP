"""
Provider-agnostic OCR interface (ingestion step 3 — image/scanned-PDF → text).

Local has no true image OCR (that's exactly why Catalyst Zia is worth it), so the
local provider only pulls text from digital PDFs; the Zia provider does real OCR of
scanned images and handwriting. Everything downstream (embed → pgvector, NER, DB
load) stays the same regardless of which provider produced the text.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class OcrProvider(ABC):
    @abstractmethod
    async def extract_text(
        self, content: bytes, filename: str, language: Optional[str] = None
    ) -> dict:
        """Return {'text': str, 'confidence': float, 'provider': str}."""
