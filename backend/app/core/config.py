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

    # ── Groq — LLM + Whisper transcription ────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"      # tool-calling / planning
    GROQ_LLM_MODEL_FAST: str = "llama-3.1-8b-instant"    # cheap narration/claim-validation pass
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"         # Kannada + English transcription

    # ── Embeddings — local, no network call (Groq has no embedding endpoint) ──
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    # ── File storage ──────────────────────────────────────────────────────────
    # /uploads maps to the named Docker volume (backend/docker-compose.yml:
    # uploads:/uploads). Using /tmp/uploads would be ephemeral — files would
    # be lost on container restart (DEBT-03 fix).
    UPLOAD_DIR: str = "/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
