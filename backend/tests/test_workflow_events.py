"""Integration tests for Phase 7 audit logging / workflow timeline."""

from app.models.employee import Employee
from app.models.enums import Department, EmploymentType, ResourceType, Sensitivity
from app.models.resource import Resource


def _create_request(client, employee_id: int, raw_query: str) -> str:
    response = client.post(
        "/api/requests", json={"employee_id": employee_id, "raw_query": raw_query}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _other_active_employee(db_session) -> Employee:
    employee = Employee(
        name="Approving Manager",
        email="timeline.manager@novatech.io",
        department=Department.HR,
        role="Manager",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


def test_timeline_records_request_created_event(client, sample_employee):
    request_id = _create_request(client, sample_employee.id, "How much PTO do I have left?")

    response = client.get(f"/api/requests/{request_id}/timeline")
    assert response.status_code == 200
    events = response.json()
    assert events[0]["event_type"] == "request_created"
    assert events[0]["actor"] == f"employee:{sample_employee.id}"


def test_timeline_records_every_node_in_order_for_a_completed_run(
    client, db_session, sample_employee
):
    resource = Resource(
        name="reporting-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.LOW
    )
    db_session.add(resource)
    db_session.commit()

    request_id = _create_request(
        client, sample_employee.id, "I need access to the reporting-db database"
    )
    client.post(f"/api/requests/{request_id}/run")

    events = client.get(f"/api/requests/{request_id}/timeline").json()
    event_types = [e["event_type"] for e in events]
    assert event_types == [
        "request_created",
        "classify",
        "retrieve_policy",
        "plan",
        "risk_check",
        "execute",
        "verify",
        "respond",
    ]
    # Chronological order.
    timestamps = [e["created_at"] for e in events]
    assert timestamps == sorted(timestamps)


def test_timeline_skips_plan_execute_verify_for_info_only_intent(client, sample_employee):
    request_id = _create_request(client, sample_employee.id, "How much PTO do I have left?")
    client.post(f"/api/requests/{request_id}/run")

    timeline = client.get(f"/api/requests/{request_id}/timeline").json()
    event_types = [e["event_type"] for e in timeline]
    assert event_types == ["request_created", "classify", "retrieve_policy", "respond"]


def test_timeline_records_approval_decision_and_apply_decision(client, db_session, sample_employee):
    resource = Resource(
        name="billing-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()
    approver = _other_active_employee(db_session)

    request_id = _create_request(client, sample_employee.id, "Can I get access to the billing-db")
    client.post(f"/api/requests/{request_id}/run")

    client.post(
        f"/api/requests/{request_id}/approve",
        json={"approver_employee_id": approver.id, "notes": "approved"},
    )

    timeline = client.get(f"/api/requests/{request_id}/timeline").json()
    event_types = [e["event_type"] for e in timeline]
    assert event_types == [
        "request_created",
        "classify",
        "retrieve_policy",
        "plan",
        "risk_check",
        "execute",
        "respond",  # end of the initial /run - tool came back PENDING_APPROVAL
        "apply_decision",
        "verify",
        "respond",  # end of the resume graph triggered by /approve
        "approval_decision",
    ]

    approval_event = next(
        e
        for e in client.get(f"/api/requests/{request_id}/timeline").json()
        if e["event_type"] == "approval_decision"
    )
    assert approval_event["actor"] == f"employee:{approver.id}"
    assert approval_event["payload"] == {"decision": "APPROVED", "notes": "approved"}


def test_timeline_records_workflow_error_without_corrupting_request_status(
    client, db_session, sample_employee
):
    approver = _other_active_employee(db_session)

    request_id = _create_request(client, sample_employee.id, "I need access to the nonexistent-db")
    ran = client.post(f"/api/requests/{request_id}/run").json()
    assert ran["status"] == "AWAITING_APPROVAL"
    assert ran["tool_execution_id"] is None  # plan was incomplete, no resource matched

    response = client.post(
        f"/api/requests/{request_id}/approve",
        json={"approver_employee_id": approver.id},
    )
    assert response.status_code == 422

    # The failed approval attempt must not have touched the request row.
    unchanged = client.get(f"/api/requests/{request_id}").json()
    assert unchanged["status"] == "AWAITING_APPROVAL"
    assert unchanged["approver_employee_id"] is None

    events = client.get(f"/api/requests/{request_id}/timeline").json()
    assert events[-1]["event_type"] == "workflow_error"
    assert "resource_name" in events[-1]["payload"]["error"]


def test_timeline_for_unknown_request_returns_404(client):
    response = client.get("/api/requests/00000000-0000-0000-0000-000000000000/timeline")
    assert response.status_code == 404
