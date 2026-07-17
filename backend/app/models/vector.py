"""Vector chunk model — one row per narrative chunk with pgvector embedding."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base
from app.models.enums import ChunkType


class VectorChunk(Base):
    """
    One record per narrative chunk stored in the vector store.
    Embedding dimension matches settings.EMBEDDING_DIM
    (default 768 for Vertex AI text-embedding-004).
    """

    __tablename__ = "vector_chunk"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"), nullable=False, index=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("case_master.id"), nullable=True, index=True)
    chunk_type: Mapped[ChunkType] = mapped_column(Enum(ChunkType), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
