"""Mock "book business travel" tool.

Encodes the approval rules from `data/policies/travel-and-expense-policy.md`:
domestic trips under $1,500 are auto-approved; anything international or
over $1,500 needs manager approval.
"""

from app.models.employee import Employee
from app.models.enums import ToolExecutionStatus
from app.tools.result import ToolResult

_AUTO_APPROVE_DOMESTIC_LIMIT_USD = 1500


def book_travel(
    employee: Employee, destination: str, is_international: bool, total_cost_usd: float
) -> ToolResult:
    details = {
        "destination": destination,
        "is_international": is_international,
        "total_cost_usd": total_cost_usd,
    }

    if not is_international and total_cost_usd < _AUTO_APPROVE_DOMESTIC_LIMIT_USD:
        return ToolResult(
            status=ToolExecutionStatus.APPROVED,
            message=f"Domestic trip to {destination} under $1,500 auto-approved.",
            details=details,
        )

    reason = "International travel" if is_international else "Trip cost of $1,500 or more"
    return ToolResult(
        status=ToolExecutionStatus.PENDING_APPROVAL,
        message=f"{reason} requires manager approval before booking.",
        details=details,
    )
