"""Mock "grant database/repo/cloud access" tool.

Encodes the approval rules from `data/policies/data-access-policy.md`:
LOW is auto-approved and standing; MEDIUM/HIGH need a (future, Phase 6)
human approval and are time-boxed; a contractor can never get standing
HIGH-sensitivity access, and even a time-boxed exception still needs
approval.
"""

from app.models.employee import Employee
from app.models.enums import EmploymentType, Sensitivity, ToolExecutionStatus
from app.models.resource import Resource
from app.tools.result import ToolResult

_DEFAULT_DURATION_DAYS: dict[Sensitivity, int | None] = {
    Sensitivity.LOW: None,  # standing access, no expiry
    Sensitivity.MEDIUM: 90,
    Sensitivity.HIGH: 30,
}


def grant_data_access(
    employee: Employee, resource: Resource, duration_days: int | None = None
) -> ToolResult:
    if (
        employee.employment_type == EmploymentType.CONTRACTOR
        and resource.sensitivity == Sensitivity.HIGH
    ):
        effective_duration = duration_days
        if effective_duration is None or effective_duration > 5:
            return ToolResult(
                status=ToolExecutionStatus.DENIED,
                message=(
                    "Contractors may never be granted standing HIGH-sensitivity access; "
                    "an exception must be explicitly time-boxed to 5 business days or fewer."
                ),
                details={"resource": resource.name, "requested_duration_days": duration_days},
            )
        return ToolResult(
            status=ToolExecutionStatus.PENDING_APPROVAL,
            message=(
                f"Time-boxed HIGH-sensitivity access for a contractor requires Security "
                f"co-approval, even at {effective_duration} day(s)."
            ),
            details={"resource": resource.name, "duration_days": effective_duration},
        )

    effective_duration = duration_days or _DEFAULT_DURATION_DAYS[resource.sensitivity]

    if resource.sensitivity == Sensitivity.LOW:
        return ToolResult(
            status=ToolExecutionStatus.APPROVED,
            message=f"Access to {resource.name!r} (LOW sensitivity) auto-approved.",
            details={"resource": resource.name, "duration_days": effective_duration},
        )

    if resource.sensitivity == Sensitivity.MEDIUM:
        return ToolResult(
            status=ToolExecutionStatus.PENDING_APPROVAL,
            message=(
                f"Access to {resource.name!r} (MEDIUM sensitivity) requires manager approval."
            ),
            details={"resource": resource.name, "duration_days": effective_duration},
        )

    return ToolResult(
        status=ToolExecutionStatus.PENDING_APPROVAL,
        message=(
            f"Access to {resource.name!r} (HIGH sensitivity) requires manager and "
            "Security approval."
        ),
        details={"resource": resource.name, "duration_days": effective_duration},
    )
