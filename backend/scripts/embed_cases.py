"""
Batch-embed existing case narratives (CaseMaster.brief_facts) into the pgvector
store so similar-case RAG (§8.1) has something to retrieve.

Seed/bridge-loaded cases set brief_facts but never go through the upload→embed
path, so the vector store starts empty. This backfills it in one pass. Idempotent:
skips cases that already have a chunk. Uses one shared provenance Document (chunks
are matched to cases via incident_id, so the document_id FK just needs to be valid).

Run:  docker compose exec api python -m scripts.embed_cases
"""

import asyncio

from sqlalchemy import select

from app.core.database import AdminSessionFactory
from app.models.case import CaseMaster
from app.models.document import Document
from app.models.enums import ChunkType, DocumentFormat, ExtractionMethod, SourceType
from app.models.vector import VectorChunk
from app.services.embedding_service import EmbeddingService

_BATCH_REF = "batch://case-brief-facts"


async def run() -> None:
    svc = EmbeddingService()
    async with AdminSessionFactory() as session:
        doc = (
            await session.execute(select(Document).where(Document.raw_file_ref == _BATCH_REF))
        ).scalar_one_or_none()
        if doc is None:
            doc = Document(
                source_type=SourceType.FIR,
                file_format=DocumentFormat.UNKNOWN,
                original_filename="case_brief_facts_batch",
                raw_file_ref=_BATCH_REF,
                extraction_method=ExtractionMethod.MANUAL,
                confidence_score=1.0,
                human_verified=True,
            )
            session.add(doc)
            await session.flush()

        already = set(
            (await session.execute(select(VectorChunk.incident_id))).scalars().all()
        )
        rows = (
            await session.execute(
                select(CaseMaster.id, CaseMaster.brief_facts).where(CaseMaster.brief_facts.isnot(None))
            )
        ).all()
        todo = [(cid, bf) for cid, bf in rows if bf and bf.strip() and cid not in already]
        if not todo:
            print("Nothing to embed (all cases with brief_facts already have chunks).")
            return

        embeddings = await asyncio.to_thread(svc._embed_texts, [bf for _, bf in todo])
        for (cid, bf), emb in zip(todo, embeddings):
            session.add(
                VectorChunk(
                    document_id=doc.id,
                    incident_id=cid,
                    chunk_type=ChunkType.GIST,
                    chunk_index=0,
                    chunk_text=bf,
                    embedding=emb,
                )
            )
        await session.commit()
        print(f"Embedded {len(todo)} case narratives into vector_chunk.")


if __name__ == "__main__":
    asyncio.run(run())
