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
from app.core.vertex_ai import init_vertex_ai

configure_logging()
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("Starting Karnataka Crime Analytics Platform", version=settings.API_VERSION)

    # ── Google Vertex AI SDK — must be first ──────────────────────────────────
    init_vertex_ai()

    # Relational DB — create tables if not present (Alembic handles migrations)
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

    # ── Routes ────────────────────────────────────────────────────────────────
    application.include_router(api_router, prefix=settings.API_PREFIX)

    # ── Metrics ───────────────────────────────────────────────────────────────
    Instrumentator().instrument(application).expose(application)

    return application


app = create_application()
