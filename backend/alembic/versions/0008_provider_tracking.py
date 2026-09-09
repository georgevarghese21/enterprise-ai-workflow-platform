"""Track which LLM provider actually answered classify/plan

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "requests", sa.Column("classifier_provider", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "requests", sa.Column("planner_provider", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("requests", "planner_provider")
    op.drop_column("requests", "classifier_provider")
