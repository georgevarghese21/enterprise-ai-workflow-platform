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


class RequestIntent(enum.StrEnum):
    """The category an employee request is classified into (Phase 3+).

    Chosen to line up 1:1 with both the fictional policy documents under
    `data/policies/` (so RAG retrieval has an obvious document to target)
    and the mock enterprise tools planned for Phase 4.
    """

    DATA_ACCESS = "DATA_ACCESS"
    IT_EQUIPMENT = "IT_EQUIPMENT"
    IT_SOFTWARE = "IT_SOFTWARE"
    TRAVEL_BOOKING = "TRAVEL_BOOKING"
    EXPENSE_REIMBURSEMENT = "EXPENSE_REIMBURSEMENT"
    TIME_OFF = "TIME_OFF"
    REMOTE_WORK = "REMOTE_WORK"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    OTHER = "OTHER"


class ToolExecutionStatus(enum.StrEnum):
    """Outcome of a mock enterprise tool call (Phase 4+).

    Mirrors the approval language used throughout `data/policies/`: a tool
    call is either auto-approved outright, left pending a human approval
    that doesn't exist yet (Phase 6 adds the actual approve/reject flow),
    or denied by a hard policy rule (e.g. a contractor requesting standing
    HIGH-sensitivity access).
    """

    APPROVED = "APPROVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DENIED = "DENIED"


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
