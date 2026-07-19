"""
Shared enumerations used across models.
Single definition point — never duplicated across files.
"""

import enum


class SourceType(str, enum.Enum):
    FIR = "FIR"
    CHARGESHEET = "CHARGESHEET"
    JUDGMENT = "JUDGMENT"
    HISTORY_SHEET = "HISTORY_SHEET"
    STATEMENT = "STATEMENT"
    NEWS = "NEWS"
    FINANCIAL = "FINANCIAL"
    GD = "GD"


class CaseStage(str, enum.Enum):
    REGISTERED = "registered"
    INVESTIGATION = "investigation"
    CHARGESHEET_FILED = "chargesheet_filed"
    DISPOSED = "disposed"
    CLOSED = "closed"


class CaseDispositionType(str, enum.Enum):
    CHARGESHEET = "Chargesheet"
    FALSE_CASE = "False Case"
    UNDETECTED = "Undetected"


class PersonRole(str, enum.Enum):
    ACCUSED = "accused"
    VICTIM = "victim"
    WITNESS = "witness"
    COMPLAINANT = "complainant"


class DocumentFormat(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    CSV = "csv"
    XLSX = "xlsx"
    HTML = "html"
    JPG = "jpg"
    PNG = "png"
    WAV = "wav"
    MP3 = "mp3"
    GEOJSON = "geojson"
    SHAPEFILE = "shapefile"
    UNKNOWN = "unknown"


class ExtractionMethod(str, enum.Enum):
    DIRECT_LOAD = "direct_load"
    TEMPLATE_EXTRACTION = "template_extraction"
    NER_RELATION = "ner_relation"
    FULL_TEXT_EMBED = "full_text_embed"
    TRANSCRIPTION = "transcription"
    GIS_LOAD = "gis_load"
    MANUAL = "manual"


class ChunkType(str, enum.Enum):
    MO = "mo"
    GIST = "gist"
    STATEMENT = "statement"
    CHARGESHEET = "chargesheet"
    NEWS = "news"


class Role(str, enum.Enum):
    """
    Karnataka Police rank hierarchy plus two specialist tracks.
    CRIME_ANALYST and POLICY_MAKER sit outside the command chain — see
    app/core/permissions.py for the capability matrix that governs access
    (a linear rank order can't express those two tracks correctly).
    """

    CONSTABLE = "CONSTABLE"
    INSPECTOR = "INSPECTOR"
    DSP = "DSP"
    SP = "SP"
    DGP = "DGP"
    CRIME_ANALYST = "CRIME_ANALYST"
    POLICY_MAKER = "POLICY_MAKER"


class Sex(str, enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"
    UNKNOWN = "U"


class FinancialAlertType(str, enum.Enum):
    STRUCTURING = "structuring"
    FUNNEL_ACCOUNT = "funnel_account"
    LAYERING = "layering"
    HIGH_VALUE = "high_value"
    ORGANIZED_CLUSTER = "organized_cluster"


class MLModelStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
