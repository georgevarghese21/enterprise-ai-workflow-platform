"""Mock "submit expense reimbursement" tool.

Encodes the approval rules from `data/policies/travel-and-expense-policy.md`:
under $100 is auto-approved, $100-$1,000 needs manager approval, and over
$1,000 needs manager + Finance approval.
"""

from app.models.employee import Employee
from app.models.enums import ToolExecutionStatus
from app.tools.result import ToolResult

_AUTO_APPROVE_LIMIT_USD = 100
_FINANCE_APPROVAL_THRESHOLD_USD = 1000


def submit_expense(employee: Employee, amount_usd: float, description: str) -> ToolResult:
    details = {"amount_usd": amount_usd, "description": description}

    if amount_usd < _AUTO_APPROVE_LIMIT_USD:
        return ToolResult(
            status=ToolExecutionStatus.APPROVED,
            message="Expense under $100 auto-approved for reimbursement.",
            details=details,
        )

    if amount_usd <= _FINANCE_APPROVAL_THRESHOLD_USD:
        return ToolResult(
            status=ToolExecutionStatus.PENDING_APPROVAL,
            message="Expense between $100 and $1,000 requires manager approval.",
            details=details,
        )

    return ToolResult(
        status=ToolExecutionStatus.PENDING_APPROVAL,
        message="Expense over $1,000 requires manager and Finance approval.",
        details=details,
    )
