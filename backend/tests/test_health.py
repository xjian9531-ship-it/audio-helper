def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert isinstance(body["request_id"], str)
    assert body["request_id"]
