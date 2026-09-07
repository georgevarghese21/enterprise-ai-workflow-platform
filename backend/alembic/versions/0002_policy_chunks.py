"""Add policy_chunks table for RAG (pgvector)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed at the value used when this migration was written. Not imported from
# app.rag.embeddings on purpose: migrations must stay reproducible even if
# that constant changes later (a dimension change needs its own migration).
EMBEDDING_DIMENSIONS = 256


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_name", "chunk_index", name="uq_policy_chunk"),
    )
    op.create_index(
        op.f("ix_policy_chunks_document_name"), "policy_chunks", ["document_name"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_policy_chunks_document_name"), table_name="policy_chunks")
    op.drop_table("policy_chunks")
