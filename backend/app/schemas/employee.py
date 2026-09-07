from pydantic import BaseModel, ConfigDict

from app.models.enums import Department, EmploymentType


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    department: Department
    role: str
    manager_id: int | None
    employment_type: EmploymentType
    location: str
    active: bool
