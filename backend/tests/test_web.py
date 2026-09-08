"""Integration tests for the Phase 8 server-rendered (Jinja2 + htmx) frontend."""

from app.models.employee import Employee
from app.models.enums import Department, EmploymentType, ResourceType, Sensitivity
from app.models.resource import Resource


def _other_active_employee(db_session) -> Employee:
    employee = Employee(
        name="Web Test Manager",
        email="web.test.manager@novatech.io",
        department=Department.HR,
        role="Manager",
        employment_type=EmploymentType.FULL_TIME,
        location="Remote",
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


def test_dashboard_loads(client, sample_employee):
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_static_stylesheet_is_served(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_new_request_form_lists_employees(client, sample_employee):
    response = client.get("/requests/new")
    assert response.status_code == 200
    assert sample_employee.name in response.text


def test_submitting_new_request_redirects_to_detail_page(client, sample_employee):
    response = client.post(
        "/requests",
        data={"employee_id": sample_employee.id, "raw_query": "How much PTO do I have left?"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/requests/")

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "Run workflow" in detail.text


def test_submitting_new_request_with_unknown_employee_404s(client):
    response = client.post(
        "/requests", data={"employee_id": 999999, "raw_query": "test"}, follow_redirects=False
    )
    assert response.status_code == 404


def test_run_workflow_via_web_completes_info_only_request(client, sample_employee):
    location = client.post(
        "/requests",
        data={"employee_id": sample_employee.id, "raw_query": "How much PTO do I have left?"},
        follow_redirects=False,
    ).headers["location"]
    request_id = location.rsplit("/", 1)[-1]

    response = client.post(f"/requests/{request_id}/run")
    assert response.status_code == 200
    assert "COMPLETED" in response.text
    assert 'id="request-content"' in response.text


def test_approvals_queue_lists_and_resolves_pending_request(client, db_session, sample_employee):
    resource = Resource(
        name="reporting-db", resource_type=ResourceType.DATABASE, sensitivity=Sensitivity.MEDIUM
    )
    db_session.add(resource)
    db_session.commit()
    approver = _other_active_employee(db_session)

    location = client.post(
        "/requests",
        data={
            "employee_id": sample_employee.id,
            "raw_query": "Can I get access to the reporting-db database",
        },
        follow_redirects=False,
    ).headers["location"]
    request_id = location.rsplit("/", 1)[-1]
    client.post(f"/requests/{request_id}/run")

    queue = client.get("/approvals")
    assert f"approval-row-{request_id}" in queue.text

    response = client.post(
        f"/requests/{request_id}/approve?view=queue",
        data={"approver_employee_id": approver.id, "notes": "fine"},
    )
    assert response.status_code == 200
    assert "COMPLETED" in response.text
    assert approver.name in response.text


def test_approval_with_incomplete_plan_shows_inline_error_not_crash(
    client, db_session, sample_employee
):
    approver = _other_active_employee(db_session)

    location = client.post(
        "/requests",
        data={
            "employee_id": sample_employee.id,
            "raw_query": "I need access to the nonexistent-db",
        },
        follow_redirects=False,
    ).headers["location"]
    request_id = location.rsplit("/", 1)[-1]
    client.post(f"/requests/{request_id}/run")

    response = client.post(
        f"/requests/{request_id}/approve?view=queue",
        data={"approver_employee_id": approver.id},
    )
    assert response.status_code == 200
    assert "resource_name" in response.text
    # Row must still show the pending approval form, not a resolved status.
    assert "Approve" in response.text


def test_employees_and_resources_pages_load(client, sample_employee, db_session):
    resource = Resource(
        name="test-resource", resource_type=ResourceType.TOOL, sensitivity=Sensitivity.LOW
    )
    db_session.add(resource)
    db_session.commit()

    employees_page = client.get("/employees")
    assert employees_page.status_code == 200
    assert sample_employee.name in employees_page.text

    resources_page = client.get("/resources")
    assert resources_page.status_code == 200
    assert "test-resource" in resources_page.text


def test_requests_list_status_filter(client, sample_employee):
    client.post(
        "/requests",
        data={"employee_id": sample_employee.id, "raw_query": "How much PTO do I have left?"},
    )
    response = client.get("/requests", params={"status": "RECEIVED"})
    assert response.status_code == 200

    bad = client.get("/requests", params={"status": "NOT_A_STATUS"})
    assert bad.status_code == 400
