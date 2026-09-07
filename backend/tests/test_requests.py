def test_create_request_for_known_employee(client, sample_employee):
    response = client.post(
        "/api/requests",
        json={"employee_id": sample_employee.id, "raw_query": "I need access to analytics-db"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["employee_id"] == sample_employee.id
    assert body["status"] == "RECEIVED"
    assert body["final_response"] is None


def test_create_request_for_unknown_employee_returns_404(client):
    response = client.post(
        "/api/requests", json={"employee_id": 999999, "raw_query": "hello"}
    )
    assert response.status_code == 404


def test_list_and_get_request(client, sample_employee):
    create_response = client.post(
        "/api/requests",
        json={"employee_id": sample_employee.id, "raw_query": "What is the remote work policy?"},
    )
    request_id = create_response.json()["id"]

    list_response = client.get("/api/requests")
    assert list_response.status_code == 200
    assert any(r["id"] == request_id for r in list_response.json())

    get_response = client.get(f"/api/requests/{request_id}")
    assert get_response.status_code == 200
    assert get_response.json()["raw_query"] == "What is the remote work policy?"


def test_get_unknown_request_returns_404(client):
    response = client.get("/api/requests/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
