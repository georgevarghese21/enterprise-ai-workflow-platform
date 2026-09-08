"""Integration tests for the Phase 5 LangGraph workflow, via /api/requests/{id}/run."""

from app.agents.nodes import WorkflowNodes
from app.models.employee import Employee
from app.models.enums import (
    Department,
    EmploymentType,
    ResourceType,
    Sensitivity,
    WorkflowStatus,
)
from app.models.resource import Resource


def _create_request(client, employee_id: int, raw_query: str) -> str:
    response = client.post(
        "/api/requests", json={"employee_id": employee_id, "raw_query": raw_query}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_data_access_low_sensitivity_completes_automatically(client, db_session, sample_employee):
    resource = Resource(
        name="reporting-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.LOW
    )
    db_session.add(resource)
    db_session.commit()

    request_id = _create_request(
        client, sample_employee.id, "I need access to the reporting-db database please"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "DATA_ACCESS"
    assert body["status"] == "COMPLETED"
    assert body["plan_tool_name"] == "grant_data_access"
    assert body["tool_execution_id"] is not None
    assert body["risk_level"] == "LOW"


def test_data_access_medium_sensitivity_awaits_approval(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()

    request_id = _create_request(
        client, sample_employee.id, "Can I get access to the billing-db database"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["status"] == "AWAITING_APPROVAL"
    assert body["tool_execution_id"] is not None


def test_contractor_high_sensitivity_data_access_is_rejected(client, db_session):
    employee = Employee(
        name="Contract Worker",
        email="contract.worker@novatech.io",
        department=Department.ENGINEERING,
        role="Contractor",
        employment_type=EmploymentType.CONTRACTOR,
        location="Remote",
    )
    resource = Resource(
        name="prod-secrets", resource_type=ResourceType.CLOUD, sensitivity=Sensitivity.HIGH
    )
    db_session.add_all([employee, resource])
    db_session.commit()
    db_session.refresh(employee)

    request_id = _create_request(
        client, employee.id, "I need standing access to prod-secrets please"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["status"] == "REJECTED"


def test_data_access_with_unrecognized_resource_awaits_approval(client, sample_employee):
    request_id = _create_request(
        client, sample_employee.id, "I need access to the nonexistent-db database"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["status"] == "AWAITING_APPROVAL"
    assert "incomplete_tool_arguments" in body["risk_flags"]


def test_info_only_intent_completes_without_a_tool(client, sample_employee):
    request_id = _create_request(
        client, sample_employee.id, "How much PTO do I have left this year?"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["intent"] == "TIME_OFF"
    assert body["status"] == "COMPLETED"
    assert body["plan_tool_name"] is None
    assert body["tool_execution_id"] is None
    assert "No automated action" in body["final_response"]


def test_inactive_employee_forces_escalation(client, db_session):
    employee = Employee(
        name="Former Employee",
        email="former.employee@novatech.io",
        department=Department.SALES,
        role="Account Executive",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
        active=False,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)

    request_id = _create_request(client, employee.id, "I need reimbursement for a $50 taxi ride")
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["status"] == "AWAITING_APPROVAL"
    assert "employee_inactive_or_not_found" in body["risk_flags"]
    assert body["risk_level"] == "HIGH"


def test_expense_reimbursement_under_limit_completes(client, sample_employee):
    request_id = _create_request(
        client, sample_employee.id, "Please reimburse my $40 taxi expense from yesterday"
    )
    response = client.post(f"/api/requests/{request_id}/run")

    body = response.json()
    assert body["intent"] == "EXPENSE_REIMBURSEMENT"
    assert body["status"] == "COMPLETED"
    assert body["plan_arguments"]["amount_usd"] == 40.0


def test_run_unknown_request_returns_404(client):
    response = client.post("/api/requests/00000000-0000-0000-0000-000000000000/run")
    assert response.status_code == 404


def test_risk_check_escalates_low_confidence_classification(db_session, sample_employee):
    """Unit-tests the low-confidence risk rule directly: the mock classifier
    never actually emits a tool-intent classification below 0.5 confidence,
    so this rule is otherwise unreachable through the mock provider's own
    output - exercised here the way a real LLM's low-confidence output would.
    """
    nodes = WorkflowNodes(db_session)
    state = {
        "employee_id": sample_employee.id,
        "confidence": 0.35,
        "plan_tool_name": None,
        "plan_arguments": {},
        "status": WorkflowStatus.PLANNED,
    }

    result = nodes.risk_check(state)

    assert result["escalate"] is True
    assert "low_classification_confidence" in result["risk_flags"]
