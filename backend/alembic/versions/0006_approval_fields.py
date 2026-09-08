"""Add Phase 6 human-in-the-loop approval fields to requests

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("approver_employee_id", sa.Integer(), nullable=True))
    op.add_column("requests", sa.Column("approval_notes", sa.Text(), nullable=True))
    op.add_column(
        "requests", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_requests_approver_employee_id",
        "requests",
        "employees",
        ["approver_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_requests_approver_employee_id"), "requests", ["approver_employee_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_requests_approver_employee_id"), table_name="requests")
    op.drop_constraint("fk_requests_approver_employee_id", "requests", type_="foreignkey")
    op.drop_column("requests", "approved_at")
    op.drop_column("requests", "approval_notes")
    op.drop_column("requests", "approver_employee_id")
