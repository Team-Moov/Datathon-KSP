"""
Embedding service — generates and stores vector chunks for narrative text (§3.1 vector layer).
Uses Vertex AI's text-embedding-005, output_dimensionality pinned to
settings.EMBEDDING_DIM (384) so the pgvector column type and every existing
vector_chunk row stay compatible — no schema change, no dimension migration.
Existing rows still need re-embedding after this swap though: a different
model's vectors aren't comparable to the old local sentence-transformers
ones even at the same dimensionality (see scripts/embed_cases.py).
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional

import structlog
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.vertex_ai_client import AiUnavailableError, get_genai_client, resilient_vertex_call
from app.models.enums import ChunkType, SourceType
from app.models.vector import VectorChunk
from app.repositories.vector_repository import VectorRepository

log = structlog.get_logger(__name__)

# Vertex AI's default per-project embedding quota is low enough that
# back-to-back full-speed batches can exhaust it mid-run (confirmed live) —
# this trades total runtime for not tripping the per-minute quota.
_BACKFILL_BATCH_REF = "batch://case-brief-facts"
_BACKFILL_BATCH_SIZE = 50
_BACKFILL_DELAY_SECONDS = 2

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

        # RETRIEVAL_DOCUMENT — asymmetric embedding tuned for "this is a
        # passage that will be searched for", distinct from the query side.
        embeddings = await self._embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")

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
        embeddings = await self._embed_texts([text], task_type="RETRIEVAL_QUERY")
        return embeddings[0]

    @staticmethod
    async def backfill_case_embeddings() -> Dict[str, Any]:
        """
        Batch-embed existing CaseMaster.brief_facts rows that predate the
        embed-on-ingest path (seed/bridge-loaded cases) or an embedding-model
        swap. Idempotent — skips cases that already have a chunk, so a failed/
        interrupted run just picks up where it left off on the next call.

        Commits per batch, not once at the end: a single all-or-nothing
        transaction meant a late-batch Vertex AI quota failure rolled back
        every earlier batch's work too (lost 1500/1502 embeddings once).
        Callable from the admin-triggered Celery task or the CLI script —
        both share this one implementation.
        """
        from app.core.database import AdminSessionFactory
        from app.models.case import CaseMaster
        from app.models.document import Document
        from app.models.enums import DocumentFormat, ExtractionMethod

        total_embedded = 0
        async with AdminSessionFactory() as session:
            doc = (
                await session.execute(select(Document).where(Document.raw_file_ref == _BACKFILL_BATCH_REF))
            ).scalar_one_or_none()
            if doc is None:
                doc = Document(
                    source_type=SourceType.FIR,
                    file_format=DocumentFormat.UNKNOWN,
                    original_filename="case_brief_facts_batch",
                    raw_file_ref=_BACKFILL_BATCH_REF,
                    extraction_method=ExtractionMethod.MANUAL,
                    confidence_score=1.0,
                    human_verified=True,
                )
                session.add(doc)
                await session.flush()
                await session.commit()

            while True:
                async with AdminSessionFactory() as batch_session:
                    already = set(
                        (await batch_session.execute(select(VectorChunk.incident_id))).scalars().all()
                    )
                    rows = (
                        await batch_session.execute(
                            select(CaseMaster.id, CaseMaster.brief_facts).where(CaseMaster.brief_facts.isnot(None))
                        )
                    ).all()
                    todo = [(cid, bf) for cid, bf in rows if bf and bf.strip() and cid not in already]

                if not todo:
                    log.info("Embedding backfill complete", total_embedded=total_embedded)
                    return {"status": "complete", "total_embedded": total_embedded}

                for batch_start in range(0, len(todo), _BACKFILL_BATCH_SIZE):
                    batch = todo[batch_start : batch_start + _BACKFILL_BATCH_SIZE]
                    try:
                        embeddings = await EmbeddingService._embed_texts(
                            [bf for _, bf in batch], task_type="RETRIEVAL_DOCUMENT"
                        )
                    except AiUnavailableError as exc:
                        log.warning(
                            "Embedding backfill stopped by a Vertex AI failure — already-embedded rows "
                            "are committed, next invocation resumes",
                            error=str(exc),
                            total_embedded=total_embedded,
                        )
                        return {"status": "stopped_will_resume", "total_embedded": total_embedded, "error": str(exc)}

                    async with AdminSessionFactory() as batch_session:
                        for (cid, bf), emb in zip(batch, embeddings):
                            batch_session.add(
                                VectorChunk(
                                    document_id=doc.id,
                                    incident_id=cid,
                                    chunk_type=ChunkType.GIST,
                                    chunk_index=0,
                                    chunk_text=bf,
                                    embedding=emb,
                                )
                            )
                        await batch_session.commit()

                    total_embedded += len(batch)
                    log.info("Embedding backfill batch committed", total_embedded=total_embedded)
                    await asyncio.sleep(_BACKFILL_DELAY_SECONDS)

    @staticmethod
    async def _embed_texts(texts: List[str], task_type: str) -> List[List[float]]:
        client = get_genai_client()
        response = await resilient_vertex_call(
            client.aio.models.embed_content,
            model=settings.EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM, task_type=task_type),
        )
        return [embedding.values for embedding in response.embeddings]

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
