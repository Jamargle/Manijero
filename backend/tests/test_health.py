from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_documented_success_response() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "manijero-backend",
    }


def test_health_is_described_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/health"]["get"]
    assert operation["summary"] == "Check service health"
    assert "HealthResponse" in operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
