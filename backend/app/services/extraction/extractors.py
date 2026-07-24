"""
Format-specific extractors — Step 2 of the ingestion pipeline (§2.4).
Each extractor is independently replaceable; the IngestionService just calls extract().
"""

import abc
from pathlib import Path
from typing import Any, Dict, List

from app.models.enums import DocumentFormat, ExtractionMethod, SourceType


class BaseExtractor(abc.ABC):
    """Protocol every extractor must satisfy."""

    method: ExtractionMethod

    @abc.abstractmethod
    async def extract(self, file_path: Path) -> Dict[str, Any]:
        """Return a normalized dict of extracted fields + 'confidence' key."""


class FIRPdfExtractor(BaseExtractor):
    """
    Layout-aware template extraction for IIF-1-shaped FIR PDFs, via the
    configured OCR provider (Zia — confirmed it handles PDFs directly, not
    just images, up to 20MB). Previously used pdfplumber directly for
    digital-text-only extraction; routing through the OCR provider instead
    means scanned/handwritten FIRs work too, not just digital ones.
    """

    method = ExtractionMethod.TEMPLATE_EXTRACTION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        from app.core.ocr import get_ocr_provider

        fields: Dict[str, Any] = {"confidence": 0.8}
        try:
            result = await get_ocr_provider().extract_text(file_path.read_bytes(), file_path.name)
            text = result.get("text", "") or ""
            fields["raw_text"] = text
            fields["brief_facts"] = text  # vector-store embedding target
            fields["narrative_text"] = text
            if result.get("confidence") is not None:
                fields["confidence"] = result["confidence"]
        except Exception as exc:
            fields["confidence"] = 0.4
            fields["extraction_error"] = str(exc)
        return fields


class ChargesheetExtractor(BaseExtractor):
    """Targeted extraction for verdict/sections + full-text embed, via the
    configured OCR provider (see FIRPdfExtractor for why)."""

    method = ExtractionMethod.FULL_TEXT_EMBED

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        from app.core.ocr import get_ocr_provider

        fields: Dict[str, Any] = {"confidence": 0.75}
        try:
            result = await get_ocr_provider().extract_text(file_path.read_bytes(), file_path.name)
            text = result.get("text", "") or ""
            fields["narrative_text"] = text
            # Rough heuristic — better version uses regex/NER
            fields["cs_type"] = "Chargesheet" if "chargesheet" in text.lower() else "Undetected"
            if result.get("confidence") is not None:
                fields["confidence"] = result["confidence"]
        except Exception as exc:
            fields["confidence"] = 0.3
            fields["extraction_error"] = str(exc)
        return fields


class HistorySheetExtractor(BaseExtractor):
    """NER + relation extraction for semi-structured history sheets."""

    method = ExtractionMethod.NER_RELATION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import json

        from google.genai import types

        from app.core.config import settings
        from app.core.vertex_ai_client import get_genai_client

        text_content = file_path.read_text(errors="replace") if file_path.suffix in (".txt", ".md") else ""
        if not text_content or not settings.VERTEX_PROJECT_ID:
            return {"confidence": 0.6, "narrative_text": text_content, "entities": {}}

        prompt = (
            "Extract all person names, locations, and organizations from the following "
            "text as JSON with keys 'persons', 'locations', 'organizations':\n\n" + text_content
        )
        try:
            response = await get_genai_client().aio.models.generate_content(
                model=settings.GEMINI_MODEL_FAST,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            try:
                entities = json.loads(response.text)
            except Exception:
                entities = {}
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


class FinancialCsvExtractor(BaseExtractor):
    """
    Schema-validated load for bank/transaction statements (§9.1) — no LLM
    needed, same philosophy as CsvExtractor. Normalizes varying real-world
    column names (from/sender_account, txn_date, amt, ...) into
    FinancialTransaction-shaped rows so a live upload actually reaches the
    `financial_transaction` table the detectors query, instead of stopping at
    a 'dataframe' key nothing downstream consumes.
    """

    method = ExtractionMethod.DIRECT_LOAD

    _COLUMN_ALIASES: Dict[str, List[str]] = {
        "from_account": ["from_account", "from", "sender_account", "debit_account", "source_account"],
        "to_account": ["to_account", "to", "receiver_account", "credit_account", "dest_account", "destination_account"],
        "amount": ["amount", "amt", "value", "txn_amount", "transaction_amount"],
        "transaction_date": ["transaction_date", "date", "txn_date", "value_date"],
        "currency": ["currency", "ccy"],
        "transaction_type": ["transaction_type", "type", "mode", "txn_type"],
        "linked_person_id": ["linked_person_id", "person_id"],
        "linked_person_name": ["linked_person_name", "person_name", "account_holder", "name", "customer_name"],
    }

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        import pandas as pd

        try:
            if file_path.suffix.lower() in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
        except Exception as exc:
            return {"confidence": 0.0, "extraction_error": str(exc)}

        col_map = self._resolve_columns(df.columns)
        required = ("from_account", "to_account", "amount", "transaction_date")
        missing = [f for f in required if f not in col_map]
        if missing:
            return {
                "confidence": 0.0,
                "extraction_error": (
                    f"Could not identify column(s) for {missing} in a financial "
                    f"upload. Columns found: {list(df.columns)}"
                ),
            }

        transactions: List[Dict[str, Any]] = []
        skipped = 0
        for _, row in df.iterrows():
            try:
                from_acc = str(row[col_map["from_account"]]).strip()
                to_acc = str(row[col_map["to_account"]]).strip()
                amount = float(row[col_map["amount"]])
                txn_date = pd.to_datetime(row[col_map["transaction_date"]]).date()
                if not from_acc or not to_acc or amount <= 0:
                    skipped += 1
                    continue
            except (ValueError, TypeError, KeyError):
                skipped += 1
                continue

            txn: Dict[str, Any] = {
                "from_account": from_acc,
                "to_account": to_acc,
                "amount": amount,
                "transaction_date": txn_date,
            }
            if "currency" in col_map and pd.notna(row[col_map["currency"]]):
                txn["currency"] = str(row[col_map["currency"]]).strip()
            if "transaction_type" in col_map and pd.notna(row[col_map["transaction_type"]]):
                txn["transaction_type"] = str(row[col_map["transaction_type"]]).strip()
            if "linked_person_id" in col_map and pd.notna(row[col_map["linked_person_id"]]):
                txn["linked_person_id"] = str(row[col_map["linked_person_id"]]).strip()
            elif "linked_person_name" in col_map and pd.notna(row[col_map["linked_person_name"]]):
                txn["linked_person_name"] = str(row[col_map["linked_person_name"]]).strip()
            transactions.append(txn)

        confidence = 1.0 if transactions and skipped == 0 else (0.7 if transactions else 0.0)
        return {
            "confidence": confidence,
            "transactions": transactions,
            "rows_total": int(len(df)),
            "rows_skipped": skipped,
        }

    @classmethod
    def _resolve_columns(cls, columns) -> Dict[str, str]:
        lower_cols = {str(c).strip().lower(): c for c in columns}
        resolved: Dict[str, str] = {}
        for field, aliases in cls._COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in lower_cols:
                    resolved[field] = lower_cols[alias]
                    break
        return resolved


class AudioExtractor(BaseExtractor):
    """
    Gemini's native audio understanding — supports Kannada and English in the
    same model, replacing Groq Whisper. The genai client is natively async, so
    unlike the old sync-Groq-SDK-in-a-worker-thread approach, this call runs
    directly on the event loop with no thread offload needed.
    """

    method = ExtractionMethod.TRANSCRIPTION

    async def extract(self, file_path: Path) -> Dict[str, Any]:
        from google.genai import types

        from app.core.config import settings
        from app.core.vertex_ai_client import get_genai_client

        mime_type = "audio/mpeg" if file_path.suffix.lower() == ".mp3" else "audio/wav"
        try:
            response = await get_genai_client().aio.models.generate_content(
                model=settings.GEMINI_MODEL_FAST,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=file_path.read_bytes(), mime_type=mime_type),
                            types.Part(text=(
                                "Transcribe this audio verbatim. It may be in Kannada or English — "
                                "preserve the original language. Return only the transcription, no commentary."
                            )),
                        ],
                    )
                ],
            )
            return {
                "confidence": 0.85,
                "narrative_text": response.text,
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
    (SourceType.FINANCIAL, DocumentFormat.CSV): FinancialCsvExtractor,
    (SourceType.FINANCIAL, DocumentFormat.XLSX): FinancialCsvExtractor,
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
