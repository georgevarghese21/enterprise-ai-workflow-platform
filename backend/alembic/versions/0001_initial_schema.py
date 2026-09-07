"""Initial schema: employees, resources, requests

Revision ID: 0001
Revises:
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "department",
            sa.Enum(
                "ENGINEERING",
                "DATA_SCIENCE",
                "IT",
                "FINANCE",
                "HR",
                "SECURITY",
                "SALES",
                name="department_enum",
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column(
            "employment_type",
            sa.Enum("FULL_TIME", "CONTRACTOR", name="employment_type_enum"),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["manager_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_employees_email"), "employees", ["email"], unique=True)
    op.create_index(op.f("ix_employees_manager_id"), "employees", ["manager_id"], unique=False)

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("DATABASE", "REPOSITORY", "CLOUD", "TOOL", name="resource_type_enum"),
            nullable=False,
        ),
        sa.Column(
            "sensitivity",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="sensitivity_enum"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resources_name"), "resources", ["name"], unique=True)

    op.create_table(
        "requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RECEIVED",
                "CLASSIFIED",
                "POLICY_RETRIEVED",
                "PLANNED",
                "AWAITING_APPROVAL",
                "EXECUTING",
                "VERIFYING",
                "COMPLETED",
                "REJECTED",
                "FAILED",
                name="workflow_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("final_response", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_requests_employee_id"), "requests", ["employee_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_requests_employee_id"), table_name="requests")
    op.drop_table("requests")
    op.drop_index(op.f("ix_resources_name"), table_name="resources")
    op.drop_table("resources")
    op.drop_index(op.f("ix_employees_manager_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_email"), table_name="employees")
    op.drop_table("employees")

    sa.Enum(name="workflow_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sensitivity_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="resource_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="employment_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="department_enum").drop(op.get_bind(), checkfirst=True)
