import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WorkflowStatus


class RequestCreate(BaseModel):
    employee_id: int
    raw_query: str = Field(min_length=1, max_length=4000)


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: int
    raw_query: str
    status: WorkflowStatus
    final_response: str | None
    created_at: datetime
    updated_at: datetime
