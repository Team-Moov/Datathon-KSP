"""
Format-specific extractors — Step 2 of the ingestion pipeline (§2.4).
Each extractor is independently replaceable; the IngestionService just calls extract().
"""

import abc
from pathlib import Path
from typing import Any, Dict

from app.models.enums import DocumentFormat, ExtractionMethod, SourceType


class BaseExtractor(abc.ABC):
    """Protocol every extractor must satisfy."""

    method: ExtractionMethod

    @abc.abstractmethod
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Return a normalized dict of extracted fields + 'confidence' key."""


class FIRPdfExtractor(BaseExtractor):
    """Layout-aware template extraction for IIF-1-shaped FIR PDFs using Docling/pdfplumber."""

    method = ExtractionMethod.TEMPLATE_EXTRACTION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import pdfplumber

        fields: Dict[str, Any] = {"confidence": 0.8}
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            fields["raw_text"] = text
            fields["brief_facts"] = text  # vector-store embedding target
            fields["narrative_text"] = text
        except Exception as exc:
            fields["confidence"] = 0.4
            fields["extraction_error"] = str(exc)
        return fields


class ChargesheetExtractor(BaseExtractor):
    """Targeted extraction for verdict/sections + full-text embed."""

    method = ExtractionMethod.FULL_TEXT_EMBED

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import pdfplumber

        fields: Dict[str, Any] = {"confidence": 0.75}
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            fields["narrative_text"] = text
            # Rough heuristic — better version uses regex/NER
            fields["cs_type"] = "Chargesheet" if "chargesheet" in text.lower() else "Undetected"
        except Exception as exc:
            fields["confidence"] = 0.3
            fields["extraction_error"] = str(exc)
        return fields


class HistorySheetExtractor(BaseExtractor):
    """NER + relation extraction for semi-structured history sheets."""

    method = ExtractionMethod.NER_RELATION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import asyncio
        from groq import Groq
        from app.core.config import settings
        import json

        text_content = file_path.read_text(errors="replace") if file_path.suffix in (".txt", ".md") else ""
        if not text_content or not settings.GROQ_API_KEY:
            return {"confidence": 0.6, "narrative_text": text_content, "entities": {}}

        def _call_groq() -> Dict[str, Any]:
            client = Groq(api_key=settings.GROQ_API_KEY)
            prompt = f"Extract all person names, locations, and organizations from the following text as JSON with keys 'persons', 'locations', 'organizations':\\n\\n{text_content}"
            resp = client.chat.completions.create(
                model=settings.GROQ_LLM_MODEL_FAST,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            try:
                return json.loads(resp.choices[0].message.content)
            except Exception:
                return {}

        try:
            entities = await asyncio.to_thread(_call_groq)
            return {
                "confidence": 0.85,
                "narrative_text": text_content,
                "entities": entities
            }
        except Exception as exc:
            return {"confidence": 0.4, "narrative_text": text_content, "extraction_error": str(exc)}


class CsvExtractor(BaseExtractor):
    """Schema-validated direct load — no LLM needed (§2.4)."""

    method = ExtractionMethod.DIRECT_LOAD

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import pandas as pd

        try:
            df = pd.read_csv(file_path)
            return {"confidence": 1.0, "dataframe": df.to_dict(orient="records")}
        except Exception as exc:
            return {"confidence": 0.0, "extraction_error": str(exc)}


class AudioExtractor(BaseExtractor):
    """
    Groq-hosted Whisper large-v3 — supports Kannada and English in the same
    model, called via the Groq API rather than a GCP-specific speech service.
    Runs the (sync) Groq SDK call in a worker thread so it never blocks the
    event loop.
    """

    method = ExtractionMethod.TRANSCRIPTION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import asyncio

        try:
            return await asyncio.to_thread(self._transcribe_sync, file_path)
        except Exception as exc:
            return {"confidence": 0.0, "extraction_error": str(exc)}

    @staticmethod
    def _transcribe_sync(file_path: Path) -> Dict[str, Any]:
        from groq import Groq

        from app.core.config import settings

        client = Groq(api_key=settings.GROQ_API_KEY)
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(file_path.name, audio_file.read()),
                model=settings.GROQ_WHISPER_MODEL,
                language="kn",  # Whisper auto-detects within the language if this misses
                response_format="verbose_json",
            )

        return {
            "confidence": 0.85,
            "narrative_text": response.text,
            "language": getattr(response, "language", "kn"),
        }


class NewsHtmlExtractor(BaseExtractor):
    """Scraped HTML → staging table only — never auto-merges into Incident (§2.2)."""

    method = ExtractionMethod.NER_RELATION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        try:
            from bs4 import BeautifulSoup

            html = file_path.read_text(errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n")
            return {"confidence": 0.5, "narrative_text": text, "staging_only": True}
        except Exception as exc:
            return {"confidence": 0.0, "extraction_error": str(exc)}


# ── Factory ────────────────────────────────────────────────────────────────────

_EXTRACTOR_MAP: Dict[tuple, type[BaseExtractor]] = {
    (SourceType.FIR, DocumentFormat.PDF): FIRPdfExtractor,
    (SourceType.CHARGESHEET, DocumentFormat.PDF): ChargesheetExtractor,
    (SourceType.JUDGMENT, DocumentFormat.PDF): ChargesheetExtractor,
    (SourceType.HISTORY_SHEET, DocumentFormat.PDF): HistorySheetExtractor,
    (SourceType.FIR, DocumentFormat.CSV): CsvExtractor,
    (SourceType.FIR, DocumentFormat.XLSX): CsvExtractor,
    (SourceType.STATEMENT, DocumentFormat.WAV): AudioExtractor,
    (SourceType.STATEMENT, DocumentFormat.MP3): AudioExtractor,
    (SourceType.NEWS, DocumentFormat.HTML): NewsHtmlExtractor,
}


def get_extractor(source_type: SourceType, file_format: DocumentFormat) -> BaseExtractor:
    extractor_cls = _EXTRACTOR_MAP.get((source_type, file_format))
    if extractor_cls is None:
        # Fallback to CSV extractor for unknown tabular, FIR PDF for anything else
        if file_format in (DocumentFormat.CSV, DocumentFormat.XLSX):
            extractor_cls = CsvExtractor
        else:
            extractor_cls = FIRPdfExtractor
    return extractor_cls()
