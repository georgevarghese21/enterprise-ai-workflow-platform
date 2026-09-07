def test_data_access_tool_endpoint(client, sample_employee, sample_resource):
    response = client.post(
        "/api/tools/data-access",
        json={"employee_id": sample_employee.id, "resource_name": sample_resource.name},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["tool_name"] == "grant_data_access"
    assert body["employee_id"] == sample_employee.id


def test_data_access_tool_unknown_resource_returns_404(client, sample_employee):
    response = client.post(
        "/api/tools/data-access",
        json={"employee_id": sample_employee.id, "resource_name": "does-not-exist"},
    )
    assert response.status_code == 404


def test_data_access_tool_unknown_employee_returns_404(client, sample_resource):
    response = client.post(
        "/api/tools/data-access",
        json={"employee_id": 999999, "resource_name": sample_resource.name},
    )
    assert response.status_code == 404


def test_it_ticket_tool_endpoint(client, sample_employee):
    response = client.post(
        "/api/tools/it-ticket",
        json={
            "employee_id": sample_employee.id,
            "category": "EQUIPMENT_STANDARD",
            "description": "Replacement laptop",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "APPROVED"


def test_travel_booking_tool_endpoint(client, sample_employee):
    response = client.post(
        "/api/tools/travel-booking",
        json={
            "employee_id": sample_employee.id,
            "destination": "Austin",
            "is_international": False,
            "total_cost_usd": 900,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "APPROVED"


def test_expense_reimbursement_tool_endpoint(client, sample_employee):
    response = client.post(
        "/api/tools/expense-reimbursement",
        json={
            "employee_id": sample_employee.id,
            "amount_usd": 2500,
            "description": "Team offsite",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert "Finance" in body["message"]


def test_list_tool_executions(client, sample_employee, sample_resource):
    client.post(
        "/api/tools/data-access",
        json={"employee_id": sample_employee.id, "resource_name": sample_resource.name},
    )
    response = client.get("/api/tools/executions")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_tool_endpoint_unknown_employee_returns_404(client):
    response = client.post(
        "/api/tools/expense-reimbursement",
        json={"employee_id": 999999, "amount_usd": 50, "description": "Taxi"},
    )
    assert response.status_code == 404


def test_data_access_tool_links_to_request(client, sample_employee, sample_resource):
    request_response = client.post(
        "/api/requests",
        json={"employee_id": sample_employee.id, "raw_query": "I need access to analytics-db"},
    )
    request_id = request_response.json()["id"]

    response = client.post(
        "/api/tools/data-access",
        json={
            "employee_id": sample_employee.id,
            "resource_name": sample_resource.name,
            "request_id": request_id,
        },
    )
    assert response.status_code == 201
    assert response.json()["request_id"] == request_id


def test_data_access_tool_unknown_request_id_returns_404(client, sample_employee, sample_resource):
    response = client.post(
        "/api/tools/data-access",
        json={
            "employee_id": sample_employee.id,
            "resource_name": sample_resource.name,
            "request_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404
