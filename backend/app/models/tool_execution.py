import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ToolExecutionStatus


class ToolExecution(Base):
    """A record of a single mock enterprise tool call (Phase 4+).

    One shared table for every tool (data access, IT tickets, travel,
    expenses, ...) rather than a table per tool, since every call has the
    same shape: an employee, a tool name, structured input, a structured
    result, and an outcome. `request_id` is nullable because tools are
    callable standalone in Phase 4; the (future) LangGraph workflow will
    set it once a tool call happens as part of a request (Phase 5+).
    """

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requests.id", ondelete="SET NULL"), nullable=True,
        index=True,
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(ToolExecutionStatus, name="tool_execution_status_enum"), nullable=False
    )
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
