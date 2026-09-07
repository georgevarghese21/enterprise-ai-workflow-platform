def test_list_resources_returns_seeded_resource(client, sample_resource):
    response = client.get("/api/resources")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "analytics-db"
