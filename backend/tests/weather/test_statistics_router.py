"""Integration tests for weather statistics HTTP router with AccuWeather integration."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.main import app
from app.routers.statistics_router import get_statistics_service
from app.schemas.weather_schema import CoverageInfo, StatisticsMetrics, WeatherStatisticsResponse
from app.services.statistics_service import StatisticsService


@pytest.fixture
def mock_stats_service() -> MagicMock:
    """Fixture providing a mock StatisticsService."""
    return MagicMock(spec=StatisticsService)


@pytest.fixture
def client(mock_stats_service: MagicMock) -> TestClient:
    """TestClient fixture with dependency override for StatisticsService."""
    app.dependency_overrides[get_statistics_service] = lambda: mock_stats_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_get_statistics_success(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test successful GET /api/v1/weather/statistics?city=Indore&period_type=week&duration=1."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="SUCCESS",
        city="Indore",
        provider="accuweather",
        period_type="week",
        duration=1,
        period_value=1,
        start_date="2026-09-25",
        end_date="2026-10-02",
        average_temperature_celsius=31.8,
        data_coverage={"complete": True},
        data_source="accuweather",
        coverage=CoverageInfo(
            requested="1 Week (7 days / 168 hours)",
            available="168 hours (100.0%)",
            complete=True,
            percent=100.0,
            observation_count=168,
        ),
        statistics=StatisticsMetrics(
            average_temperature=31.8,
        ),
        average_temperature=31.8,
        coverage_percent=100.0,
        observation_count=168,
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=week&duration=1")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["city"] == "Indore"
    assert data["provider"] == "accuweather"
    assert data["period_type"] == "week"
    assert data["duration"] == 1
    assert data["average_temperature_celsius"] == 31.8
    assert data["data_coverage"]["complete"] is True


def test_get_statistics_insufficient_data(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test GET /api/v1/weather/statistics returning insufficient data payload."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="INSUFFICIENT_HISTORICAL_DATA",
        city="Indore",
        provider="accuweather",
        period_type="month",
        duration=12,
        period_value=12,
        start_date="2025-10-02",
        end_date="2026-10-02",
        average_temperature_celsius=None,
        data_coverage={"complete": False},
        data_source="accuweather",
        coverage=CoverageInfo(
            requested="12 Months",
            available="24 hours",
            complete=False,
            percent=0.3,
            observation_count=24,
        ),
        statistics=None,
        message="Historical weather data is not available for the complete requested period.",
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=month&duration=12")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "INSUFFICIENT_HISTORICAL_DATA"
    assert data["city"] == "Indore"
    assert data["provider"] == "accuweather"
    assert data["duration"] == 12
    assert data["data_coverage"]["complete"] is False
    assert data["average_temperature_celsius"] is None
    assert "not available" in data["message"].lower()


def test_get_statistics_year_removed(client: TestClient) -> None:
    """Test GET /api/v1/weather/statistics with period=year fails because Year option is removed."""
    response = client.get("/api/v1/weather/statistics?city=Indore&period=year")
    assert response.status_code == 400
    data = response.json()
    assert "year" in data["detail"].lower()
    assert "removed" in data["detail"].lower()


def test_get_statistics_invalid_period(client: TestClient) -> None:
    """Test GET /api/v1/weather/statistics with unsupported period fails validation."""
    response = client.get("/api/v1/weather/statistics?city=Indore&period=century")
    assert response.status_code == 400
    data = response.json()
    assert "Invalid statistics period" in data["detail"]


def test_get_statistics_invalid_duration(client: TestClient) -> None:
    """Test duration validation in router: week supports 1-4, month supports 1-12."""
    # Week: 5 is invalid
    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=week&duration=5")
    assert response.status_code == 400
    assert "Invalid week duration" in response.json()["detail"]

    # Month: 13 is invalid
    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=month&duration=13")
    assert response.status_code == 400
    assert "Invalid month duration" in response.json()["detail"]

    # Month: 6 and 12 are valid
    mock_response = WeatherStatisticsResponse(
        status="SUCCESS",
        city="Indore",
        provider="accuweather",
        period_type="month",
        duration=6,
        data_coverage={"complete": True},
        coverage=CoverageInfo(complete=True),
        average_temperature_celsius=32.0,
    )
    # Testing that 6 is accepted without 400
    # Client query param
    app.dependency_overrides[get_statistics_service] = lambda: MagicMock(
        calculate_average_weather=MagicMock(return_value=mock_response)
    )
    res_valid = client.get("/api/v1/weather/statistics?city=Indore&period_type=month&duration=6")
    assert res_valid.status_code == 200


def test_get_statistics_empty_city(client: TestClient) -> None:
    """Test empty city query param fails validation."""
    response = client.get("/api/v1/weather/statistics?city=%20%20&period=week")
    assert response.status_code == 400
    assert "City name cannot be empty" in response.json()["detail"]


def test_get_statistics_city_not_found(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test CityNotFoundError maps to HTTP 404."""
    mock_stats_service.calculate_average_weather.side_effect = CityNotFoundError("City 'Nonexistent' not found.")

    response = client.get("/api/v1/weather/statistics?city=Nonexistent&period=week")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_statistics_auth_error(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test WeatherAuthenticationError maps to HTTP 503."""
    mock_stats_service.calculate_average_weather.side_effect = WeatherAuthenticationError("AccuWeather auth failed.")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 503
    assert "authentication failed" in response.json()["detail"].lower()


def test_get_statistics_rate_limit(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test WeatherRateLimitError maps to HTTP 429."""
    mock_stats_service.calculate_average_weather.side_effect = WeatherRateLimitError("Rate limit exceeded.")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_get_statistics_timeout(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test WeatherTimeoutError maps to HTTP 504."""
    mock_stats_service.calculate_average_weather.side_effect = WeatherTimeoutError("Request timed out.")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_get_statistics_service_unavailable(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test WeatherServiceUnavailableError maps to HTTP 503."""
    mock_stats_service.calculate_average_weather.side_effect = WeatherServiceUnavailableError("Service down.")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_get_statistics_internal_error(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test unhandled exception yields HTTP 500 without leaking stack traces."""
    mock_stats_service.calculate_average_weather.side_effect = RuntimeError("Internal memory fault")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 500
    assert "An error occurred while calculating weather statistics" in response.json()["detail"]
