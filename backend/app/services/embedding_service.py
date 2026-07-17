"""
Embedding service — generates and stores vector chunks for narrative text (§3.1 vector layer).
Uses Google Vertex AI text-embedding-004 (768-dim) via langchain-google-vertexai.
Authenticated via Application Default Credentials (ADC) — no API key needed when
running on GCP; set GOOGLE_APPLICATION_CREDENTIALS for local dev with a SA key file.
"""

import uuid
from typing import List, Optional

import structlog
from langchain_google_vertexai import VertexAIEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import ChunkType, SourceType
from app.models.vector import VectorChunk
from app.repositories.vector_repository import VectorRepository

log = structlog.get_logger(__name__)

# Chunk size in characters (~512 tokens at ~4 chars/token)
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

# SourceType → ChunkType mapping
_CHUNK_TYPE_MAP = {
    SourceType.FIR: ChunkType.GIST,
    SourceType.CHARGESHEET: ChunkType.CHARGESHEET,
    SourceType.JUDGMENT: ChunkType.CHARGESHEET,
    SourceType.STATEMENT: ChunkType.STATEMENT,
    SourceType.NEWS: ChunkType.NEWS,
    SourceType.HISTORY_SHEET: ChunkType.MO,
}


class EmbeddingService:
    def __init__(self) -> None:
        # VertexAIEmbeddings uses ADC automatically when running on GCP.
        # Locally, export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
        self._embedder = VertexAIEmbeddings(
            model_name=settings.EMBEDDING_MODEL,   # text-embedding-004
            project=settings.GCP_PROJECT,
            location=settings.GCP_LOCATION,
        )

    async def embed_and_store(
        self,
        text: str,
        document_id: uuid.UUID,
        incident_id: Optional[uuid.UUID],
        chunk_type: SourceType,
        db: AsyncSession,
    ) -> List[VectorChunk]:
        chunks = self._split_text(text)
        repo = VectorRepository(db)
        stored_chunks = []

        # VertexAIEmbeddings.aembed_documents handles batching internally
        embeddings = await self._embedder.aembed_documents(chunks)

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = VectorChunk(
                document_id=document_id,
                incident_id=incident_id,
                chunk_type=_CHUNK_TYPE_MAP.get(chunk_type, ChunkType.GIST),
                chunk_index=idx,
                chunk_text=chunk_text,
                embedding=embedding,
            )
            stored = await repo.upsert_chunk(chunk)
            stored_chunks.append(stored)

        log.info(
            "Chunks embedded and stored",
            document_id=str(document_id),
            num_chunks=len(stored_chunks),
            model=settings.EMBEDDING_MODEL,
        )
        return stored_chunks

    async def embed_query(self, text: str) -> List[float]:
        """Embed a query string for similarity search — no storage."""
        return await self._embedder.aembed_query(text)

    @staticmethod
    def _split_text(text: str) -> List[str]:
        """Simple sliding-window chunker."""
        if len(text) <= CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks
