def test_list_employees_returns_seeded_employee(client, sample_employee):
    response = client.get("/api/employees")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "jordan.lee@novatech.io"


def test_get_employee_by_id(client, sample_employee):
    response = client.get(f"/api/employees/{sample_employee.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Jordan Lee"


def test_get_unknown_employee_returns_404(client):
    response = client.get("/api/employees/999999")
    assert response.status_code == 404
