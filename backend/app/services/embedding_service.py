"""
Embedding service — generates and stores vector chunks for narrative text (§3.1 vector layer).
Uses a local sentence-transformers model (all-MiniLM-L6-v2, 384-dim) rather than a
hosted embedding API — Groq doesn't serve an embedding endpoint, and running this
locally means the only network-dependent LLM calls left in the system are the
chat/narration ones (conversation_service, investigator_support).
"""

import asyncio
import uuid
from typing import List, Optional

import structlog
from sentence_transformers import SentenceTransformer
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

# Loaded once per process — sentence-transformers is a heavyweight sync model
# load; every embed call runs it via asyncio.to_thread so it never blocks the
# event loop.
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        model_name = settings.EMBEDDING_MODEL.removeprefix("sentence-transformers/")
        _model = SentenceTransformer(model_name)
        log.info("Local embedding model loaded", model=model_name, dim=settings.EMBEDDING_DIM)
    return _model


class EmbeddingService:
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

        embeddings = await asyncio.to_thread(self._embed_texts, chunks)

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
        embeddings = await asyncio.to_thread(self._embed_texts, [text])
        return embeddings[0]

    @staticmethod
    def _embed_texts(texts: List[str]) -> List[List[float]]:
        model = _get_model()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

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
