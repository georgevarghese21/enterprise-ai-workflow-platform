import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkflowEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    event_type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime
