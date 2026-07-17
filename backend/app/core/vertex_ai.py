"""
Vertex AI SDK initialisation — called once at startup from main.py lifespan.
Sets project + location globally so every ChatVertexAI / VertexAIEmbeddings
instance picks them up without needing to pass credentials repeatedly.
Uses Application Default Credentials (ADC):
  - On GCP (Cloud Run / GKE / Compute Engine): Workload Identity / instance metadata.
  - Local dev: GOOGLE_APPLICATION_CREDENTIALS env var pointing to a SA key JSON.
"""

import os

import structlog
import vertexai

from app.core.config import settings

log = structlog.get_logger(__name__)


def init_vertex_ai() -> None:
    """
    Initialise the Vertex AI SDK.
    Must be called before any model or embedding is instantiated.
    """
    sa_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if sa_path:
        # Explicit SA key — useful for local development
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", sa_path)
        log.info("Vertex AI: using explicit service account key", path=sa_path)
    else:
        log.info("Vertex AI: using Application Default Credentials (ADC)")

    vertexai.init(
        project=settings.GCP_PROJECT,
        location=settings.GCP_LOCATION,
    )
    log.info(
        "Vertex AI initialised",
        project=settings.GCP_PROJECT,
        location=settings.GCP_LOCATION,
        llm_model=settings.LLM_MODEL,
        flash_model=settings.LLM_MODEL_FLASH,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dim=settings.EMBEDDING_DIM,
    )
