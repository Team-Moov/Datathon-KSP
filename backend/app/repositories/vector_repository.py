"""
Vector repository — semantic similarity search over VectorChunk using pgvector.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import ChunkType
from app.models.vector import VectorChunk
from app.repositories.base import BaseRepository


class VectorRepository(BaseRepository[VectorChunk]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(VectorChunk, db)

    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        chunk_type: Optional[ChunkType] = None,
        incident_id: Optional[UUID] = None,
    ) -> List[VectorChunk]:
        """
        Cosine similarity search via pgvector <=> operator.
        Returns top_k most similar chunks.
        """
        filters = []
        if chunk_type:
            filters.append(f"chunk_type = '{chunk_type.value}'")
        if incident_id:
            filters.append(f"incident_id = '{incident_id}'")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        stmt = text(f"""
            SELECT id FROM vector_chunk
            {where_clause}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)
        result = await self.db.execute(
            stmt,
            {"embedding": str(query_embedding), "top_k": top_k},
        )
        ids = [row[0] for row in result.fetchall()]

        if not ids:
            return []

        chunks_stmt = select(VectorChunk).where(VectorChunk.id.in_(ids))
        chunks_result = await self.db.execute(chunks_stmt)
        chunks = {str(c.id): c for c in chunks_result.scalars().all()}
        # Preserve similarity order
        return [chunks[str(i)] for i in ids if str(i) in chunks]

    async def upsert_chunk(self, chunk: VectorChunk) -> VectorChunk:
        self.db.add(chunk)
        await self.db.flush()
        await self.db.refresh(chunk)
        return chunk
