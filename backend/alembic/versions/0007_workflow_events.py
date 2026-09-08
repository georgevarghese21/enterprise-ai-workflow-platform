"""Add workflow_events table for Phase 7 audit logging / timeline

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workflow_events_request_id"), "workflow_events", ["request_id"], unique=False
    )
    op.create_index(
        op.f("ix_workflow_events_created_at"), "workflow_events", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_events_created_at"), table_name="workflow_events")
    op.drop_index(op.f("ix_workflow_events_request_id"), table_name="workflow_events")
    op.drop_table("workflow_events")
