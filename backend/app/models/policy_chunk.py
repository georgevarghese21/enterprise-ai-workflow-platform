from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.rag.embeddings import EMBEDDING_DIMENSIONS


class PolicyChunk(Base):
    """A retrievable chunk of a NovaTech policy document, embedded for RAG.

    Documents under `data/policies/` are split into chunks (roughly one per
    section) by `app.rag.ingest`, embedded via the configured embedding
    provider, and stored here so `app.rag.retrieve` can run a pgvector
    similarity search against them.
    """

    __tablename__ = "policy_chunks"
    __table_args__ = (UniqueConstraint("document_name", "chunk_index", name="uq_policy_chunk"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
