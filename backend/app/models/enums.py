import enum


class Department(enum.StrEnum):
    ENGINEERING = "ENGINEERING"
    DATA_SCIENCE = "DATA_SCIENCE"
    IT = "IT"
    FINANCE = "FINANCE"
    HR = "HR"
    SECURITY = "SECURITY"
    SALES = "SALES"


class EmploymentType(enum.StrEnum):
    FULL_TIME = "FULL_TIME"
    CONTRACTOR = "CONTRACTOR"


class ResourceType(enum.StrEnum):
    DATABASE = "DATABASE"
    REPOSITORY = "REPOSITORY"
    CLOUD = "CLOUD"
    TOOL = "TOOL"


class Sensitivity(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WorkflowStatus(enum.StrEnum):
    """Lifecycle of a single employee request as it moves through the
    (future) LangGraph workflow. Phase 1 only ever sets RECEIVED; later
    phases advance the status as the agentic workflow progresses.
    """

    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    POLICY_RETRIEVED = "POLICY_RETRIEVED"
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
