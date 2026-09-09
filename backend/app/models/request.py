import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.employee import Employee
from app.models.enums import RequestIntent, RiskLevel, WorkflowStatus


class Request(Base):
    """A single employee request submitted to the AI assistant.

    This is the row that the LangGraph workflow (Phase 5+) attaches its
    classification, retrieved evidence, tool plan, risk assessment, and
    final response to. Phase 1 only supported creating and reading
    requests; `POST /api/requests/{id}/run` (Phase 5) is what actually
    advances `status` and fills in the rest of these columns end to end.
    """

    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum"),
        nullable=False,
        default=WorkflowStatus.RECEIVED,
    )
    intent: Mapped[RequestIntent | None] = mapped_column(
        Enum(RequestIntent, name="request_intent_enum"), nullable=True
    )
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    classifier_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retrieved_policy: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    plan_tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan_arguments: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    planner_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, name="risk_level_enum"), nullable=True
    )
    risk_flags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    tool_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tool_executions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_requests_tool_execution_id",
        ),
        nullable=True,
    )
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    employee: Mapped[Employee] = relationship("Employee", foreign_keys=[employee_id])
