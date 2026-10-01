"""Unit tests for system health endpoint and root status."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a test client for the FastAPI application."""
    return TestClient(app)


def test_health_check_status_code(client: TestClient) -> None:
    """Test that GET /health returns HTTP 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_payload_exact(client: TestClient) -> None:
    """Test that GET /health returns exactly {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint(client: TestClient) -> None:
    """Test that GET / returns application information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "docs" in data
    assert "health" in data
