"""Pure unit tests for the mock tool business logic - no DB needed."""

from app.models.employee import Employee
from app.models.enums import (
    Department,
    EmploymentType,
    ResourceType,
    Sensitivity,
    ToolExecutionStatus,
)
from app.models.resource import Resource
from app.tools.data_access import grant_data_access
from app.tools.expense import submit_expense
from app.tools.it_ticket import ITTicketCategory, create_it_ticket
from app.tools.travel import book_travel


def _employee(employment_type: EmploymentType = EmploymentType.FULL_TIME) -> Employee:
    return Employee(
        name="Test Employee",
        email="test.employee@novatech.io",
        department=Department.ENGINEERING,
        role="Engineer",
        employment_type=employment_type,
        location="Remote",
    )


def _resource(sensitivity: Sensitivity, name: str = "test-resource") -> Resource:
    return Resource(name=name, resource_type=ResourceType.DATABASE, sensitivity=sensitivity)


def test_grant_data_access_low_sensitivity_auto_approved():
    result = grant_data_access(_employee(), _resource(Sensitivity.LOW))
    assert result.status == ToolExecutionStatus.APPROVED
    assert result.details["duration_days"] is None


def test_grant_data_access_medium_sensitivity_pending_with_default_duration():
    result = grant_data_access(_employee(), _resource(Sensitivity.MEDIUM))
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL
    assert result.details["duration_days"] == 90


def test_grant_data_access_high_sensitivity_pending_with_default_duration():
    result = grant_data_access(_employee(), _resource(Sensitivity.HIGH))
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL
    assert result.details["duration_days"] == 30


def test_grant_data_access_contractor_standing_high_sensitivity_denied():
    result = grant_data_access(_employee(EmploymentType.CONTRACTOR), _resource(Sensitivity.HIGH))
    assert result.status == ToolExecutionStatus.DENIED


def test_grant_data_access_contractor_long_duration_high_sensitivity_denied():
    result = grant_data_access(
        _employee(EmploymentType.CONTRACTOR), _resource(Sensitivity.HIGH), duration_days=10
    )
    assert result.status == ToolExecutionStatus.DENIED


def test_grant_data_access_contractor_short_duration_high_sensitivity_pending():
    result = grant_data_access(
        _employee(EmploymentType.CONTRACTOR), _resource(Sensitivity.HIGH), duration_days=5
    )
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL


def test_create_it_ticket_standard_equipment_approved():
    result = create_it_ticket(_employee(), ITTicketCategory.EQUIPMENT_STANDARD, "New laptop")
    assert result.status == ToolExecutionStatus.APPROVED


def test_create_it_ticket_non_standard_equipment_under_threshold_pending():
    result = create_it_ticket(
        _employee(), ITTicketCategory.EQUIPMENT_NON_STANDARD, "Extra monitor",
        equipment_cost_usd=500,
    )
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL
    assert "Finance" not in result.message


def test_create_it_ticket_non_standard_equipment_over_threshold_mentions_finance():
    result = create_it_ticket(
        _employee(), ITTicketCategory.EQUIPMENT_NON_STANDARD, "GPU workstation",
        equipment_cost_usd=3000,
    )
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL
    assert "Finance" in result.message


def test_create_it_ticket_preapproved_software_approved():
    result = create_it_ticket(_employee(), ITTicketCategory.SOFTWARE_PREAPPROVED, "VS Code")
    assert result.status == ToolExecutionStatus.APPROVED


def test_create_it_ticket_new_software_pending():
    result = create_it_ticket(_employee(), ITTicketCategory.SOFTWARE_NEW, "New SaaS tool")
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL


def test_book_travel_domestic_under_limit_approved():
    result = book_travel(_employee(), "Austin", is_international=False, total_cost_usd=800)
    assert result.status == ToolExecutionStatus.APPROVED


def test_book_travel_domestic_over_limit_pending():
    result = book_travel(_employee(), "New York", is_international=False, total_cost_usd=2000)
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL


def test_book_travel_international_pending():
    result = book_travel(_employee(), "Tokyo", is_international=True, total_cost_usd=500)
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL


def test_submit_expense_under_100_approved():
    result = submit_expense(_employee(), 50, "Taxi")
    assert result.status == ToolExecutionStatus.APPROVED


def test_submit_expense_100_to_1000_pending():
    result = submit_expense(_employee(), 500, "Hotel incidental")
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL


def test_submit_expense_over_1000_pending_mentions_finance():
    result = submit_expense(_employee(), 2000, "Conference sponsorship")
    assert result.status == ToolExecutionStatus.PENDING_APPROVAL
    assert "Finance" in result.message
