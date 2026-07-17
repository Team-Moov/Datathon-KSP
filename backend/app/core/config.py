"""Application-wide configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
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

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "karnataka_crime"

    @property
    def DATABASE_URL(self) -> str:  # async
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

    # ── Google Cloud / Vertex AI ───────────────────────────────────────────────
    GCP_PROJECT: str                         # e.g. "my-gcp-project-id"
    GCP_LOCATION: str = "us-central1"        # Vertex AI region
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # path to SA JSON; empty = ADC

    # Gemini model identifiers (Vertex AI)
    LLM_MODEL: str = "gemini-1.5-pro-002"   # primary reasoning model
    LLM_MODEL_FLASH: str = "gemini-1.5-flash-002"  # fast/cheap narration tasks
    EMBEDDING_MODEL: str = "text-embedding-004"  # Vertex AI text embeddings
    EMBEDDING_DIM: int = 768                 # text-embedding-004 output dimension

    # ── File storage ──────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/tmp/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
