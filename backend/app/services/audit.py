"""Audit/timeline logging for the request workflow (Phase 7).

`record_workflow_event` writes one immutable row per interesting thing that
happens to a request. Most events come from `app.workflows.graph`, which
streams the LangGraph run node-by-node and logs each node's output as it
happens (event_type = the node's name); a couple of events are logged
directly by the API layer for things that happen outside the graph
(`request_created`, `approval_decision`).
"""

import enum
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow_event import WorkflowEvent


def _json_safe(value: Any) -> Any:
    """Recursively coerce a workflow-state fragment into JSON-safe values.

    Node return values can contain `StrEnum` members (`RequestIntent`,
    `WorkflowStatus`, `ToolExecutionStatus`, `RiskLevel`) and `UUID`s, neither
    of which every JSON/JSONB encoder is guaranteed to handle the way we
    want, so this makes the payload explicit rather than relying on
    `StrEnum` also happening to be a `str` subclass.
    """
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def record_workflow_event(
    db: Session,
    request_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    actor: str = "system",
) -> WorkflowEvent:
    event = WorkflowEvent(
        request_id=request_id,
        event_type=event_type,
        actor=actor,
        payload=_json_safe(payload),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
