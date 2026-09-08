"""Integration tests for Phase 6 human-in-the-loop approval (pause/resume)."""

from app.models.employee import Employee
from app.models.enums import Department, EmploymentType, ResourceType, Sensitivity
from app.models.resource import Resource


def _create_and_run(client, employee_id: int, raw_query: str) -> dict:
    response = client.post(
        "/api/requests", json={"employee_id": employee_id, "raw_query": raw_query}
    )
    request_id = response.json()["id"]
    response = client.post(f"/api/requests/{request_id}/run")
    return response.json()


def _other_active_employee(db_session, department=Department.HR) -> Employee:
    employee = Employee(
        name="Approving Manager",
        email="approving.manager@novatech.io",
        department=department,
        role="Manager",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


def test_pending_approval_queue_lists_awaiting_requests(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()

    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")
    assert body["status"] == "AWAITING_APPROVAL"

    response = client.get("/api/requests/pending-approval")
    ids = [r["id"] for r in response.json()]
    assert body["id"] in ids


def test_approve_tool_level_pending_completes_and_updates_tool_execution(
    client, db_session, sample_employee
):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()
    approver = _other_active_employee(db_session)

    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")
    tool_execution_id = body["tool_execution_id"]
    assert tool_execution_id is not None

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": approver.id, "notes": "looks fine"},
    )
    approved = response.json()
    assert response.status_code == 200
    assert approved["status"] == "COMPLETED"
    assert approved["approver_employee_id"] == approver.id
    assert "human reviewer" in approved["final_response"]

    executions = client.get("/api/tools/executions").json()
    execution = next(e for e in executions if e["id"] == tool_execution_id)
    assert execution["status"] == "APPROVED"


def test_reject_tool_level_pending_marks_denied(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()
    approver = _other_active_employee(db_session)

    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")
    tool_execution_id = body["tool_execution_id"]

    response = client.post(
        f"/api/requests/{body['id']}/reject",
        json={"approver_employee_id": approver.id},
    )
    rejected = response.json()
    assert rejected["status"] == "REJECTED"

    executions = client.get("/api/tools/executions").json()
    execution = next(e for e in executions if e["id"] == tool_execution_id)
    assert execution["status"] == "DENIED"


def test_approve_pre_execution_escalation_with_missing_plan_argument_fails_cleanly(
    client, db_session, sample_employee
):
    """No tool ran yet (risk_check escalated with `incomplete_tool_arguments`
    because no resource name could be matched in the request text).
    Approving can't conjure up the missing resource name, so it must fail
    with a clear, actionable error rather than crashing.
    """
    approver = _other_active_employee(db_session)

    body = _create_and_run(client, sample_employee.id, "I need access to the nonexistent-db")
    assert body["status"] == "AWAITING_APPROVAL"
    assert body["tool_execution_id"] is None
    assert "incomplete_tool_arguments" in body["risk_flags"]

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": approver.id},
    )
    assert response.status_code == 422
    assert "resource_name" in response.json()["detail"]


def test_approve_pre_execution_escalation_for_inactive_employee(client, db_session):
    resource = Resource(
        name="reporting-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.LOW
    )
    employee = Employee(
        name="Former Employee",
        email="former.employee2@novatech.io",
        department=Department.SALES,
        role="Account Executive",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
        active=False,
    )
    db_session.add_all([resource, employee])
    db_session.commit()
    db_session.refresh(employee)
    approver = _other_active_employee(db_session)

    body = _create_and_run(client, employee.id, "I need access to the reporting-db database")
    assert body["status"] == "AWAITING_APPROVAL"
    assert body["tool_execution_id"] is None
    assert body["plan_tool_name"] == "grant_data_access"

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": approver.id},
    )
    approved = response.json()
    assert response.status_code == 200
    assert approved["status"] == "COMPLETED"
    assert approved["tool_execution_id"] is not None


def test_cannot_approve_own_request(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()

    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": sample_employee.id},
    )
    assert response.status_code == 400


def test_cannot_approve_non_awaiting_request(client, db_session, sample_employee):
    approver = _other_active_employee(db_session)
    body = _create_and_run(client, sample_employee.id, "How much PTO do I have left?")
    assert body["status"] == "COMPLETED"

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": approver.id},
    )
    assert response.status_code == 409


def test_approve_with_unknown_approver_returns_404(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()
    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": 999999},
    )
    assert response.status_code == 404


def test_inactive_approver_is_rejected(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    inactive_approver = Employee(
        name="Inactive Approver",
        email="inactive.approver@novatech.io",
        department=Department.HR,
        role="Manager",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
        active=False,
    )
    db_session.add_all([resource, inactive_approver])
    db_session.commit()
    db_session.refresh(inactive_approver)

    body = _create_and_run(client, sample_employee.id, "Can I get access to the billing-db")

    response = client.post(
        f"/api/requests/{body['id']}/approve",
        json={"approver_employee_id": inactive_approver.id},
    )
    assert response.status_code == 400
