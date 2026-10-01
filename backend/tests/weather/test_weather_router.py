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


def test_get_forecast_success(client: TestClient, mock_service: MagicMock) -> None:
    """Test successful GET /api/v1/weather/forecast?city=Indore&days=5."""
    from app.schemas.weather_schema import ForecastDay, ForecastResponse
    mock_service.get_forecast.return_value = ForecastResponse(
        city="Indore",
        forecast=[
            ForecastDay(
                date="2026-10-02",
                temperature_min=24.5,
                temperature_max=32.1,
                condition="Sunny",
                precipitation_probability=20,
                humidity=60,
                wind_speed=12.4,
            )
        ],
        resolved_address="Indore, Madhya Pradesh, India",
    )

    response = client.get("/api/v1/weather/forecast?city=Indore&days=5")
    assert response.status_code == 200
    data = response.json()

    assert data["city"] == "Indore"
    assert len(data["forecast"]) == 1
    day = data["forecast"][0]
    assert day["date"] == "2026-10-02"
    assert day["temperature_min"] == 24.5
    assert day["temperature_max"] == 32.1
    assert day["condition"] == "Sunny"
    assert day["precipitation_probability"] == 20
    assert day["humidity"] == 60
    assert day["wind_speed"] == 12.4


def test_get_forecast_empty_city(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast with empty city returns 400 Bad Request."""
    mock_service.get_forecast.side_effect = ValueError("City name cannot be empty.")
    response = client.get("/api/v1/weather/forecast?city=%20&days=5")
    assert response.status_code == 400
    assert "City name cannot be empty" in response.json()["detail"]


def test_get_forecast_invalid_days_zero(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast with days=0 returns 400 Bad Request."""
    mock_service.get_forecast.side_effect = ValueError("Forecast days must be between 1 and 10.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=0")
    assert response.status_code == 400


def test_get_forecast_invalid_days_negative(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast with days=-1 returns 400 Bad Request."""
    mock_service.get_forecast.side_effect = ValueError("Forecast days must be between 1 and 10.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=-1")
    assert response.status_code == 400


def test_get_forecast_invalid_days_unsupported_range(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast with days=15 returns 400 Bad Request."""
    mock_service.get_forecast.side_effect = ValueError("Forecast days must be between 1 and 10.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=15")
    assert response.status_code == 400


def test_get_forecast_invalid_days_string(client: TestClient) -> None:
    """Test GET /api/v1/weather/forecast with days=abc returns 422 Unprocessable Entity."""
    response = client.get("/api/v1/weather/forecast?city=Indore&days=abc")
    assert response.status_code == 422


def test_get_forecast_city_not_found(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast returns 404 when city cannot be found."""
    mock_service.get_forecast.side_effect = CityNotFoundError("City 'Unknown' not found.")
    response = client.get("/api/v1/weather/forecast?city=Unknown&days=5")
    assert response.status_code == 404


def test_get_forecast_auth_failure(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast returns 503 on auth error."""
    mock_service.get_forecast.side_effect = WeatherAuthenticationError("Auth failed.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=5")
    assert response.status_code == 503


def test_get_forecast_timeout(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast returns 504 on timeout."""
    mock_service.get_forecast.side_effect = WeatherTimeoutError("Timeout.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=5")
    assert response.status_code == 504


def test_get_forecast_service_unavailable(client: TestClient, mock_service: MagicMock) -> None:
    """Test GET /api/v1/weather/forecast returns 503 on service unavailable."""
    mock_service.get_forecast.side_effect = WeatherServiceUnavailableError("Unavailable.")
    response = client.get("/api/v1/weather/forecast?city=Indore&days=5")
    assert response.status_code == 503

