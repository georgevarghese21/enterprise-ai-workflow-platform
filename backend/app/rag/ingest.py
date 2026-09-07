"""Ingest NovaTech policy documents into the `policy_chunks` table for RAG.

Run with `python -m app.rag.ingest`. Idempotent: re-ingesting a document
replaces its existing chunks (matched by `document_name`) rather than
duplicating them, so this is safe to re-run whenever the policy documents
or the embedding provider change.
"""

import logging
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.policy_chunk import PolicyChunk
from app.rag.chunking import chunk_markdown
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


def ingest_document(db: Session, path: Path, provider: EmbeddingProvider) -> int:
    text = path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text)

    db.execute(delete(PolicyChunk).where(PolicyChunk.document_name == path.name))
    for index, chunk in enumerate(chunks):
        embedding = provider.embed(f"{chunk.title or ''}\n{chunk.content}")
        db.add(
            PolicyChunk(
                document_name=path.name,
                title=chunk.title,
                chunk_index=index,
                content=chunk.content,
                embedding=embedding,
            )
        )
    return len(chunks)


def run_ingest() -> None:
    settings = get_settings()
    policies_dir = Path(settings.policies_dir)
    provider = get_embedding_provider()

    paths = sorted(policies_dir.glob("*.md"))
    if not paths:
        logger.warning("No policy documents found in %s", policies_dir)
        return

    total_chunks = 0
    with SessionLocal() as db:
        for path in paths:
            total_chunks += ingest_document(db, path, provider)
        db.commit()

    logger.info("Ingested %d chunks from %d policy documents", total_chunks, len(paths))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingest()
