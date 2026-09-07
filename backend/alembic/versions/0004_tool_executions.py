"""Add tool_executions table for mock enterprise tools

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("APPROVED", "PENDING_APPROVAL", "DENIED", name="tool_execution_status_enum"),
            nullable=False,
        ),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tool_executions_request_id"), "tool_executions", ["request_id"], unique=False
    )
    op.create_index(
        op.f("ix_tool_executions_employee_id"), "tool_executions", ["employee_id"], unique=False
    )
    op.create_index(
        op.f("ix_tool_executions_tool_name"), "tool_executions", ["tool_name"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_executions_tool_name"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_employee_id"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_request_id"), table_name="tool_executions")
    op.drop_table("tool_executions")
    sa.Enum(name="tool_execution_status_enum").drop(op.get_bind(), checkfirst=True)
