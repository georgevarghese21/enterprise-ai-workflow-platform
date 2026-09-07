import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ToolExecutionStatus
from app.tools.it_ticket import ITTicketCategory


class DataAccessToolRequest(BaseModel):
    employee_id: int
    resource_name: str
    duration_days: int | None = Field(default=None, ge=1)
    request_id: uuid.UUID | None = None


class ITTicketToolRequest(BaseModel):
    employee_id: int
    category: ITTicketCategory
    description: str = Field(min_length=1, max_length=2000)
    equipment_cost_usd: float | None = Field(default=None, ge=0)
    request_id: uuid.UUID | None = None


class TravelBookingToolRequest(BaseModel):
    employee_id: int
    destination: str = Field(min_length=1, max_length=255)
    is_international: bool = False
    total_cost_usd: float = Field(ge=0)
    request_id: uuid.UUID | None = None


class ExpenseToolRequest(BaseModel):
    employee_id: int
    amount_usd: float = Field(ge=0)
    description: str = Field(min_length=1, max_length=2000)
    request_id: uuid.UUID | None = None


class ToolExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID | None
    employee_id: int
    tool_name: str
    status: ToolExecutionStatus
    input_payload: dict[str, Any]
    result_payload: dict[str, Any]
    message: str
    created_at: datetime
