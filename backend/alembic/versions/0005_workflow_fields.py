"""Add Phase 5 LangGraph workflow fields to requests

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

risk_level_enum = sa.Enum("LOW", "MEDIUM", "HIGH", name="risk_level_enum")


def upgrade() -> None:
    risk_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("requests", sa.Column("retrieved_policy", postgresql.JSONB(), nullable=True))
    op.add_column("requests", sa.Column("plan_tool_name", sa.String(length=100), nullable=True))
    op.add_column("requests", sa.Column("plan_arguments", postgresql.JSONB(), nullable=True))
    op.add_column("requests", sa.Column("risk_level", risk_level_enum, nullable=True))
    op.add_column("requests", sa.Column("risk_flags", postgresql.JSONB(), nullable=True))
    op.add_column(
        "requests", sa.Column("tool_execution_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_requests_tool_execution_id",
        "requests",
        "tool_executions",
        ["tool_execution_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_requests_tool_execution_id", "requests", type_="foreignkey")
    op.drop_column("requests", "tool_execution_id")
    op.drop_column("requests", "risk_flags")
    op.drop_column("requests", "risk_level")
    op.drop_column("requests", "plan_arguments")
    op.drop_column("requests", "plan_tool_name")
    op.drop_column("requests", "retrieved_policy")
    risk_level_enum.drop(op.get_bind(), checkfirst=True)
