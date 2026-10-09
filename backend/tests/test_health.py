def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "VoltPlan" in data["app"]
    assert data["ai_provider"] == "mock"
    assert data["default_standard"] == "RS IEC 60364"


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "VoltPlan" in data["app"]
    assert data["docs"] == "/docs"
