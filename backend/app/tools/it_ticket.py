"""Mock "file an IT ticket" tool.

Encodes the approval rules from `data/policies/it-equipment-and-software-policy.md`:
standard equipment and pre-approved software are auto-fulfilled; anything
else needs manager approval, plus Finance above $2,000.
"""

import enum

from app.models.employee import Employee
from app.models.enums import ToolExecutionStatus
from app.tools.result import ToolResult

_NON_STANDARD_APPROVAL_THRESHOLD_USD = 2000


class ITTicketCategory(enum.StrEnum):
    EQUIPMENT_STANDARD = "EQUIPMENT_STANDARD"
    EQUIPMENT_NON_STANDARD = "EQUIPMENT_NON_STANDARD"
    SOFTWARE_PREAPPROVED = "SOFTWARE_PREAPPROVED"
    SOFTWARE_NEW = "SOFTWARE_NEW"


def create_it_ticket(
    employee: Employee,
    category: ITTicketCategory,
    description: str,
    equipment_cost_usd: float | None = None,
) -> ToolResult:
    details = {"category": category.value, "description": description}
    if equipment_cost_usd is not None:
        details["equipment_cost_usd"] = equipment_cost_usd

    if category == ITTicketCategory.EQUIPMENT_STANDARD:
        return ToolResult(
            status=ToolExecutionStatus.APPROVED,
            message="Standard equipment request auto-approved; IT will fulfill within 2 "
            "business days.",
            details=details,
        )

    if category == ITTicketCategory.SOFTWARE_PREAPPROVED:
        return ToolResult(
            status=ToolExecutionStatus.APPROVED,
            message="Pre-approved software request auto-approved, subject to seat availability.",
            details=details,
        )

    if category == ITTicketCategory.SOFTWARE_NEW:
        return ToolResult(
            status=ToolExecutionStatus.PENDING_APPROVAL,
            message="New software requires Security review (typically 3-5 business days).",
            details=details,
        )

    # EQUIPMENT_NON_STANDARD
    message = "Non-standard equipment requires manager approval."
    if equipment_cost_usd is not None and equipment_cost_usd > _NON_STANDARD_APPROVAL_THRESHOLD_USD:
        message += " Cost exceeds $2,000, so Finance approval is also required."
    return ToolResult(
        status=ToolExecutionStatus.PENDING_APPROVAL,
        message=message,
        details=details,
    )
