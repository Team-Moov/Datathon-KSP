"""
Karnataka Crime Analytics Platform — Backend
Entry point for the FastAPI application.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.graph_db import graph_db
from app.core.logging import configure_logging
from app.core.vertex_ai_client import init_vertex_ai
from app.core.request_context import RequestContextMiddleware

configure_logging()
log = structlog.get_logger(__name__)


def _guard_against_mock_mfa_in_production() -> None:
    """
    ALLOW_MOCK_MFA=True hands OTP codes back in the API response — acceptable for
    local/demo use, unacceptable the moment ENVIRONMENT=production. A misconfigured
    .env shouldn't be how that gets discovered, so startup refuses outright.
    """
    if settings.ENVIRONMENT == "production" and settings.ALLOW_MOCK_MFA:
        log.error(
            "Refusing to start: ALLOW_MOCK_MFA=True with ENVIRONMENT=production — "
            "this would return live OTP codes in plaintext API responses"
        )
        raise RuntimeError("ALLOW_MOCK_MFA must be False when ENVIRONMENT=production")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("Starting Karnataka Crime Analytics Platform", version=settings.API_VERSION)

    _guard_against_mock_mfa_in_production()

    # ── Vertex AI client — must be first ───────────────────────────────────────
    init_vertex_ai()

    # Relational DB — create tables if not present, then run any pending
    # numbered schema_upgrades.py steps past schema_version (see that module).
    await init_db()

    # Graph DB connection pool
    await graph_db.connect()

    log.info("All connections healthy — ready to serve")
    yield

    # Graceful teardown
    await graph_db.close()
    await engine.dispose()
    log.info("Shutdown complete")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="Intelligent Conversational AI & Crime Analytics Platform — Karnataka Police",
        version=settings.API_VERSION,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request context (audit trail / change history source of ip+user-agent) ─
    application.add_middleware(RequestContextMiddleware)

    # ── Routes ────────────────────────────────────────────────────────────────
    application.include_router(api_router, prefix=settings.API_PREFIX)

    # ── Metrics ───────────────────────────────────────────────────────────────
    Instrumentator().instrument(application).expose(application)

    return application


app = create_application()
