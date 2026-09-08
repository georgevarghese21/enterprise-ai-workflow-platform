"""Shared state schema for the LangGraph employee-request workflow (Phase 5+).

Each node in `app.workflows.graph` reads/writes a subset of this state.
LangGraph merges partial dict updates a node returns into the running state
using each field's default (overwrite) reducer, which is what every field
here needs: nothing in this workflow accumulates across nodes, each field is
written wholesale by exactly one node.
"""

from typing import Any, TypedDict
from uuid import UUID

from app.models.enums import RequestIntent, RiskLevel, ToolExecutionStatus, WorkflowStatus


class WorkflowState(TypedDict, total=False):
    # Set once at graph invocation.
    request_id: UUID
    employee_id: int
    raw_query: str

    # Set by `classify`.
    intent: RequestIntent | None
    confidence: float | None
    reasoning: str | None

    # Set by `retrieve_policy`.
    retrieved_chunks: list[dict[str, Any]]

    # Set by `plan` (only reached for tool-having intents).
    plan_tool_name: str | None
    plan_arguments: dict[str, Any]
    plan_notes: str

    # Set by `risk_check`.
    risk_level: RiskLevel | None
    risk_flags: list[str]
    escalate: bool

    # Set by `execute`.
    tool_execution_id: UUID | None
    tool_status: ToolExecutionStatus | None

    # Updated by every node; finalized by `respond`.
    status: WorkflowStatus
    final_response: str | None
