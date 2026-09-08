"""Shared persistence for mock enterprise tool calls.

Used by both `app.api.tools` (calling a tool directly) and the LangGraph
workflow's `execute` node (Phase 5+), so every tool call is logged to
`tool_executions` the same way regardless of how it was triggered.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.tool_execution import ToolExecution
from app.tools.result import ToolResult


def persist_tool_execution(
    db: Session,
    tool_name: str,
    employee_id: int,
    request_id: uuid.UUID | None,
    input_payload: dict,
    result: ToolResult,
) -> ToolExecution:
    execution = ToolExecution(
        request_id=request_id,
        employee_id=employee_id,
        tool_name=tool_name,
        status=result.status,
        input_payload=input_payload,
        result_payload=result.details,
        message=result.message,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution
