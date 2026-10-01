"""Integration tests for weather router HTTP endpoints."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.main import app
from app.routers.weather_router import get_weather_service
from app.schemas.weather_schema import WeatherResponse
from app.services.weather_service import WeatherService


@pytest.fixture
def mock_service() -> MagicMock:
    """Fixture providing a mock WeatherService."""
    return MagicMock(spec=WeatherService)


@pytest.fixture
def client(mock_service: MagicMock) -> TestClient:
    """TestClient fixture with dependency override for WeatherService."""
    app.dependency_overrides[get_weather_service] = lambda: mock_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_get_current_weather_success(client: TestClient, mock_service: MagicMock) -> None:
    """Test successful GET /api/v1/weather/current?city=Indore."""
    mock_service.get_current_weather.return_value = WeatherResponse(
        city="Indore",
        temperature=28.4,
        feels_like=30.1,
        humidity=65,
        wind_speed=12.2,
        condition="Partly Cloudy",
        observed_at="2026-10-01T10:30:00",
        resolved_address="Indore, Madhya Pradesh, India",
    )

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 200
    data = response.json()

    assert data["city"] == "Indore"
    assert data["temperature"] == 28.4
    assert data["feels_like"] == 30.1
    assert data["humidity"] == 65
    assert data["wind_speed"] == 12.2
    assert data["condition"] == "Partly Cloudy"
    assert data["observed_at"] == "2026-10-01T10:30:00"


def test_get_current_weather_empty_city(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current with empty city returns 400 Bad Request."""
    mock_service.get_current_weather.side_effect = ValueError("City name cannot be empty.")

    response = client.get("/api/v1/weather/current?city=%20")
    assert response.status_code == 400
    data = response.json()
    assert "City name cannot be empty" in data["detail"]


def test_get_current_weather_invalid_city(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current with numbers-only returns 400 Bad Request."""
    mock_service.get_current_weather.side_effect = ValueError("City name must contain alphabetic characters.")

    response = client.get("/api/v1/weather/current?city=12345")
    assert response.status_code == 400
    data = response.json()
    assert "alphabetic characters" in data["detail"]


def test_get_current_weather_city_not_found(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 404 when city cannot be found."""
    mock_service.get_current_weather.side_effect = CityNotFoundError("City 'Atlantis' not found.")

    response = client.get("/api/v1/weather/current?city=Atlantis")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


def test_get_current_weather_auth_error(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 503 on API key/auth failure without exposing key."""
    mock_service.get_current_weather.side_effect = WeatherAuthenticationError("API key not configured.")

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 503
    data = response.json()
    assert "authentication failed or API key is not configured" in data["detail"]


def test_get_current_weather_rate_limit(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 429 when rate limit is exceeded."""
    mock_service.get_current_weather.side_effect = WeatherRateLimitError("Rate limit exceeded.")

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 429
    data = response.json()
    assert "rate limit exceeded" in data["detail"]


def test_get_current_weather_timeout(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 504 on provider timeout."""
    mock_service.get_current_weather.side_effect = WeatherTimeoutError("Request timed out.")

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 504
    data = response.json()
    assert "timed out" in data["detail"]


def test_get_current_weather_service_unavailable(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 503 on provider service failure."""
    mock_service.get_current_weather.side_effect = WeatherServiceUnavailableError("Service unavailable.")

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 503
    data = response.json()
    assert "currently unavailable" in data["detail"]


def test_get_current_weather_parsing_error(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/current returns 502 on malformed provider response."""
    mock_service.get_current_weather.side_effect = WeatherResponseParsingError("Malformed JSON.")

    response = client.get("/api/v1/weather/current?city=Indore")
    assert response.status_code == 502
    data = response.json()
    assert "invalid response from weather provider" in data["detail"]
