"""Similarity search over ingested policy chunks (pgvector cosine distance)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy_chunk import PolicyChunk
from app.rag.embeddings import get_embedding_provider


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: PolicyChunk
    score: float


def search_policy_chunks(db: Session, query: str, top_k: int = 5) -> list[RetrievedChunk]:
    provider = get_embedding_provider()
    query_embedding = provider.embed(query)

    distance = PolicyChunk.embedding.cosine_distance(query_embedding)
    rows = db.execute(
        select(PolicyChunk, distance.label("distance")).order_by(distance).limit(top_k)
    ).all()

    return [RetrievedChunk(chunk=row[0], score=1.0 - row[1]) for row in rows]
