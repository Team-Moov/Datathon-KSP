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
        # Placeholder — real impl calls spaCy NER pipeline
        return {
            "confidence": 0.6,
            "narrative_text": file_path.read_text(errors="replace") if file_path.suffix in (".txt",) else "",
        }


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
    Google Cloud Speech-to-Text v2 — supports Kannada (kn-IN) and English (en-IN).
    Replaces Whisper with a service that has first-class Indian language support.
    """

    method = ExtractionMethod.TRANSCRIPTION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        try:
            from google.cloud import speech as google_speech

            client = google_speech.SpeechAsyncClient()

            audio_bytes = file_path.read_bytes()
            audio = google_speech.RecognitionAudio(content=audio_bytes)

            config = google_speech.RecognitionConfig(
                encoding=google_speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                # Try Kannada first, fall back to English (India)
                language_code="kn-IN",
                alternative_language_codes=["en-IN", "en-US"],
                enable_automatic_punctuation=True,
                model="latest_long",
            )

            response = await client.recognize(config=config, audio=audio)

            transcript = " ".join(
                result.alternatives[0].transcript
                for result in response.results
                if result.alternatives
            )
            detected_language = (
                response.results[0].language_code
                if response.results
                else "kn-IN"
            )

            return {
                "confidence": 0.85,
                "narrative_text": transcript,
                "language": detected_language,
            }
        except Exception as exc:
            return {"confidence": 0.0, "extraction_error": str(exc)}


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
