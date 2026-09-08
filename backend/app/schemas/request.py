import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestIntent, RiskLevel, WorkflowStatus


class RequestCreate(BaseModel):
    employee_id: int
    raw_query: str = Field(min_length=1, max_length=4000)


class ApprovalDecisionRequest(BaseModel):
    approver_employee_id: int
    notes: str | None = Field(default=None, max_length=2000)


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: int
    raw_query: str
    status: WorkflowStatus
    intent: RequestIntent | None
    classification_confidence: float | None
    classification_reasoning: str | None
    retrieved_policy: list[dict[str, Any]] | None
    plan_tool_name: str | None
    plan_arguments: dict[str, Any] | None
    risk_level: RiskLevel | None
    risk_flags: list[str] | None
    tool_execution_id: uuid.UUID | None
    final_response: str | None
    approver_employee_id: int | None
    approval_notes: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
