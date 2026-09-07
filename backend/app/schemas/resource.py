from pydantic import BaseModel, ConfigDict

from app.models.enums import ResourceType, Sensitivity


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    resource_type: ResourceType
    sensitivity: Sensitivity
    description: str | None
