"""
Document type/format classifier — Step 1 of the ingestion pipeline (§2.4).
Determines SourceType and DocumentFormat before choosing an extraction strategy.
"""

from pathlib import Path
from typing import Tuple

from app.models.enums import DocumentFormat, SourceType

# Extension → DocumentFormat mapping
_EXT_FORMAT_MAP: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".doc": DocumentFormat.DOCX,
    ".csv": DocumentFormat.CSV,
    ".xlsx": DocumentFormat.XLSX,
    ".xls": DocumentFormat.XLSX,
    ".html": DocumentFormat.HTML,
    ".htm": DocumentFormat.HTML,
    ".jpg": DocumentFormat.JPG,
    ".jpeg": DocumentFormat.JPG,
    ".png": DocumentFormat.PNG,
    ".wav": DocumentFormat.WAV,
    ".mp3": DocumentFormat.MP3,
    ".geojson": DocumentFormat.GEOJSON,
    ".shp": DocumentFormat.SHAPEFILE,
}

# Filename hint keywords → SourceType
_FILENAME_HINTS: list[Tuple[list[str], SourceType]] = [
    (["fir", "e-fir", "efir", "first_information"], SourceType.FIR),
    (["chargesheet", "charge_sheet"], SourceType.CHARGESHEET),
    (["judgment", "verdict", "court_order"], SourceType.JUDGMENT),
    (["history_sheet", "biodata", "accused_bio"], SourceType.HISTORY_SHEET),
    (["statement", "witness", "victim_stmt"], SourceType.STATEMENT),
    (["news", "article", "media"], SourceType.NEWS),
    (["transaction", "financial", "bank"], SourceType.FINANCIAL),
    (["gd", "general_diary"], SourceType.GD),
]


class DocumentClassifier:
    """
    Rule-based classifier — no LLM needed for format detection.
    Tabular formats (CSV/XLSX) → direct load, no LLM (§2.4).
    """

    async def classify(
        self, file_path: Path, original_filename: str
    ) -> Tuple[SourceType, DocumentFormat]:
        file_format = _EXT_FORMAT_MAP.get(file_path.suffix.lower(), DocumentFormat.UNKNOWN)

        # Fast path for image / audio / geo — format determines type
        if file_format in (DocumentFormat.JPG, DocumentFormat.PNG):
            return SourceType.FIR, file_format
        if file_format in (DocumentFormat.WAV, DocumentFormat.MP3):
            return SourceType.STATEMENT, file_format
        if file_format in (DocumentFormat.GEOJSON, DocumentFormat.SHAPEFILE):
            return SourceType.FIR, file_format

        # Filename-hint matching (case-insensitive)
        lower_name = original_filename.lower()
        for keywords, source_type in _FILENAME_HINTS:
            if any(kw in lower_name for kw in keywords):
                return source_type, file_format

        # CSV/XLSX with no filename hint — sniff the header row for a
        # financial-transaction shape (account + amount columns) before
        # falling back to the FIR/generic tabular path, since most real bank
        # exports don't say "bank"/"transaction" in the filename.
        if file_format in (DocumentFormat.CSV, DocumentFormat.XLSX):
            if await self._looks_financial(file_path, file_format):
                return SourceType.FINANCIAL, file_format
            return SourceType.FIR, file_format  # will be disambiguated by schema validation

        return SourceType.FIR, file_format  # safe default — FIR pipeline is most general

    @staticmethod
    async def _looks_financial(file_path: Path, file_format: DocumentFormat) -> bool:
        try:
            if file_format == DocumentFormat.CSV:
                import csv

                with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
                    header = next(csv.reader(f), [])
            else:
                import pandas as pd

                header = list(pd.read_excel(file_path, nrows=0).columns)
        except Exception:
            return False

        lower = {str(h).strip().lower() for h in header}
        has_account = any("account" in h for h in lower)
        has_amount = any(h in ("amount", "amt", "value") or "amount" in h for h in lower)
        return has_account and has_amount
