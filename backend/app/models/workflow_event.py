import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowEvent(Base):
    """One step of a request's audit trail / workflow timeline (Phase 7+).

    Written by `app.services.audit.record_workflow_event` as the LangGraph
    workflow streams through its nodes (see `app.workflows.graph`), plus a
    couple of API-level events (`request_created`, `approval_decision`) for
    things that happen outside the graph itself. Append-only: nothing ever
    updates or deletes a row here, so a request's full history survives even
    if its `Request` row is later overwritten by a subsequent run (e.g. a
    second approval cycle after a tool call comes back PENDING_APPROVAL a
    second time).
    """

    __tablename__ = "workflow_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"), nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
