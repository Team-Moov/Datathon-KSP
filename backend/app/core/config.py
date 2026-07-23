"""Application-wide configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Meta ──────────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "Karnataka Crime Analytics Platform"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MFA is simulated until a real SMS/email provider is wired in — see
    # app/services/mfa_service.py. Must never be True in a production environment;
    # main.py's startup check enforces this.
    ALLOW_MOCK_MFA: bool = True
    OTP_EXPIRE_MINUTES: int = 5

    # Extension point for IP-based geo-restriction (app/core/geo_policy.py) —
    # permissive no-op until a real geo-IP data source is configured.
    # Stored as a raw comma-separated string, not a List field: pydantic-settings
    # tries to JSON-decode any List-typed env var before a field_validator ever
    # sees it, which throws on a plain "IN,US" value. A str field + computed
    # property sidesteps that entirely and works on any pydantic-settings version.
    ALLOWED_COUNTRIES_RAW: str = Field(default="", validation_alias="ALLOWED_COUNTRIES")

    @property
    def ALLOWED_COUNTRIES(self) -> List[str]:
        return [c.strip() for c in self.ALLOWED_COUNTRIES_RAW.split(",") if c.strip()]

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS_RAW: str = Field(default="", validation_alias="ALLOWED_ORIGINS")

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    # POSTGRES_USER/PASSWORD is the superuser/table-owner — used only for one-time
    # DDL at startup (create_all, schema_upgrades, RLS policy setup). It is NOT
    # what the running app queries through, because a superuser/table-owner
    # connection bypasses Postgres Row-Level Security entirely — the RLS district
    # policies in init_db() would be silent no-ops if the app queried as this
    # role. POSTGRES_APP_USER is the restricted, non-owner role RLS actually
    # applies to; DATABASE_URL (used by get_db/AsyncSessionFactory) connects as
    # that role, while DATABASE_URL_ADMIN (used only inside init_db) connects as
    # the superuser.
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "karnataka_crime"

    # No default — a hardcoded fallback password here would mean anyone who
    # forgets to set this in .env silently ships with a publicly-known
    # credential for the role that (per the RLS design above) is the one
    # actually granted table access. Required, same as POSTGRES_PASSWORD.
    POSTGRES_APP_USER: str = "app_runtime"
    POSTGRES_APP_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:  # async — restricted role, RLS-enforced
        return (
            f"postgresql+asyncpg://{self.POSTGRES_APP_USER}:{self.POSTGRES_APP_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_ADMIN(self) -> str:  # async — superuser, DDL/init only
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:  # for Alembic
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Vertex AI — Gemini (chat/tool-calling) + Gemini Live (voice) ──────────
    # Replaces Groq. Auth is via Application Default Credentials — either a
    # service-account JSON pointed to by GOOGLE_APPLICATION_CREDENTIALS, or the
    # ambient identity when running on GCP compute (AppSail has no ADC of its
    # own, so a service-account key is required there).
    VERTEX_PROJECT_ID: str = ""
    VERTEX_LOCATION: str = "us-central1"  # Gemini Live's region availability is narrower than text Gemini — verify against current docs before deploying
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # path to service-account JSON; google-genai picks this up via ADC automatically if set
    GEMINI_MODEL: str = "gemini-2.5-flash"            # tool-calling / planning (was GROQ_LLM_MODEL)
    GEMINI_MODEL_FAST: str = "gemini-2.5-flash-lite"  # cheap narration/claim-validation pass (was GROQ_LLM_MODEL_FAST)
    GEMINI_LIVE_MODEL: str = "gemini-2.0-flash-live-preview-04-09"  # real-time duplex voice — verify current model id before deploying, Live model names churn

    # ── Embeddings — Vertex AI ──────────────────────────────────────────────────
    # output_dimensionality is pinned to EMBEDDING_DIM at call time (see
    # embedding_service.py) so this stays whatever the pgvector column actually
    # is — changing EMBEDDING_DIM requires a schema + full re-embed, not just a
    # config edit.
    EMBEDDING_MODEL: str = "text-embedding-005"
    EMBEDDING_DIM: int = 384

    # ── File storage ──────────────────────────────────────────────────────────
    # /uploads maps to the named Docker volume (backend/docker-compose.yml:
    # uploads:/uploads). Using /tmp/uploads would be ephemeral — files would
    # be lost on container restart (DEBT-03 fix).
    UPLOAD_DIR: str = "/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── Object storage provider ───────────────────────────────────────────────
    # "local" (filesystem volume) by default; "catalyst_stratus" or "gcs" bind the
    # respective managed backends without touching call sites. See app/core/storage.
    STORAGE_PROVIDER: str = "local"
    STRATUS_BUCKET: str = ""
    STRATUS_BASE_URL: str = ""  # bucket domain, e.g. https://crime-development.zohostratus.in

    # ── Google Cloud Storage (STORAGE_PROVIDER=gcs) ───────────────────────────
    GCS_BUCKET: str = ""
    GCS_PROJECT_ID: str = ""  # falls back to VERTEX_PROJECT_ID if unset

    # ── Catalyst (Stratus / future services) admin credentials ────────────────
    # Data center is "in" for this account (accounts.zoho.in / api.catalyst.zoho.in).
    # Client id/secret from a Self Client at api-console.zoho.in; refresh token minted
    # with the Stratus scopes. Only needed when STORAGE_PROVIDER=catalyst_stratus.
    CATALYST_DC: str = "in"
    CATALYST_API_BASE: str = ""  # override host if the default api.catalyst.zoho.<dc> differs
    CATALYST_PROJECT_ID: str = ""
    CATALYST_CLIENT_ID: str = ""
    CATALYST_CLIENT_SECRET: str = ""
    CATALYST_REFRESH_TOKEN: str = ""

    # ── Cache provider ────────────────────────────────────────────────────────
    # "redis" (default) or "catalyst" (Catalyst Cache). Segment auto-discovered
    # if CATALYST_CACHE_SEGMENT is left blank.
    CACHE_PROVIDER: str = "redis"
    CATALYST_CACHE_SEGMENT: str = ""

    # ── PDF renderer ──────────────────────────────────────────────────────────
    # "local" (xhtml2pdf) or "smartbrowz" (Catalyst SmartBrowz, headless Chromium).
    PDF_PROVIDER: str = "local"
    SMARTBROWZ_PDF_URL: str = ""  # override the default …/baas/v1/project/{id}/pdf

    # ── OCR renderer ──────────────────────────────────────────────────────────
    # "zia" (Catalyst Zia OCR) — the only provider; the local pdfplumber-based
    # (digital-PDF-only, no real OCR) option was removed once Zia covered
    # everything it did and more.
    OCR_PROVIDER: str = "zia"

    # ── NER provider ──────────────────────────────────────────────────────────
    # "zia" (Catalyst Zia — verified lower recall on Indian-name narrative text)
    # or "gemini" (Vertex AI structured extraction, default). The local spaCy
    # option was removed along with the spacy/torch/transformers dependencies.
    NLP_PROVIDER: str = "gemini"

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
