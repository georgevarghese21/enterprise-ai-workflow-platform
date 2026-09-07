"""Add classification columns to requests

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


request_intent_enum = sa.Enum(
    "DATA_ACCESS",
    "IT_EQUIPMENT",
    "IT_SOFTWARE",
    "TRAVEL_BOOKING",
    "EXPENSE_REIMBURSEMENT",
    "TIME_OFF",
    "REMOTE_WORK",
    "SECURITY_INCIDENT",
    "OTHER",
    name="request_intent_enum",
)


def upgrade() -> None:
    # Unlike `create_table`, `add_column` on an existing table does not
    # implicitly issue `CREATE TYPE` for an Enum column, so it must be
    # created explicitly first.
    request_intent_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("requests", sa.Column("intent", request_intent_enum, nullable=True))
    op.add_column("requests", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("requests", sa.Column("classification_reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("requests", "classification_reasoning")
    op.drop_column("requests", "classification_confidence")
    op.drop_column("requests", "intent")
    request_intent_enum.drop(op.get_bind(), checkfirst=True)
