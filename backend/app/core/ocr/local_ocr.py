"""Local OCR provider — extracts text from digital PDFs; no image OCR (that's Zia's job)."""

from __future__ import annotations

import asyncio
import io
from typing import Optional

from app.core.ocr.base import OcrProvider


class LocalOcrProvider(OcrProvider):
    async def extract_text(
        self, content: bytes, filename: str, language: Optional[str] = None
    ) -> dict:
        if filename.lower().endswith(".pdf"):
            text = await asyncio.to_thread(self._pdf_text, content)
            return {"text": text, "confidence": 1.0 if text.strip() else 0.0, "provider": "local"}
        return {
            "text": "",
            "confidence": 0.0,
            "provider": "local",
            "note": "Local OCR only reads digital PDFs; use OCR_PROVIDER=zia for scanned images/handwriting.",
        }

    @staticmethod
    def _pdf_text(content: bytes) -> str:
        import pdfplumber

        parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
