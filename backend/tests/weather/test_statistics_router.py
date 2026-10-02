"""Integration tests for weather statistics HTTP router."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.clients.weather_client import (
    CityNotFoundError,
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
    """Test successful GET /api/v1/weather/statistics?city=Indore&period_type=week&period_value=1."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="SUCCESS",
        city="Indore",
        period_type="week",
        period_value=1,
        start_date="2026-09-25",
        end_date="2026-10-02",
        data_source="google_weather_api",
        coverage=CoverageInfo(
            requested="1 Week (7 days / 168 hours)",
            available="168 hours (100.0%)",
            complete=True,
            percent=100.0,
            observation_count=168,
        ),
        statistics=StatisticsMetrics(
            average_temperature=28.4,
            minimum_temperature=23.1,
            maximum_temperature=33.7,
            average_feels_like_temperature=30.1,
            average_humidity=61.2,
            average_wind_speed=11.8,
            total_precipitation=12.4,
        ),
        average_temperature=28.4,
        minimum_temperature=23.1,
        maximum_temperature=33.7,
        total_precipitation=12.4,
        coverage_percent=100.0,
        observation_count=168,
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=week&period_value=1")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["city"] == "Indore"
    assert data["period_type"] == "week"
    assert data["period_value"] == 1
    assert data["coverage"]["complete"] is True
    assert data["statistics"]["average_temperature"] == 28.4
    assert data["statistics"]["minimum_temperature"] == 23.1
    assert data["statistics"]["maximum_temperature"] == 33.7
    assert data["statistics"]["total_precipitation"] == 12.4


def test_get_statistics_insufficient_data(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test GET /api/v1/weather/statistics returning insufficient data payload."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="INSUFFICIENT_HISTORICAL_DATA",
        city="Indore",
        period_type="month",
        period_value=4,
        start_date="2026-06-02",
        end_date="2026-10-02",
        data_source="google_weather_api",
        coverage=CoverageInfo(
            requested="4 Months (122 days / 2928 hours)",
            available="24 hours (0.8%)",
            complete=False,
            percent=0.8,
            observation_count=24,
        ),
        statistics=None,
        message="There is not enough historical weather data available for the requested period.",
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=month&period_value=4")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "INSUFFICIENT_HISTORICAL_DATA"
    assert data["city"] == "Indore"
    assert data["coverage"]["complete"] is False
    assert data["statistics"] is None
    assert "not enough" in data["message"].lower()


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
    """Test duration validation in router."""
    # Week supports only 1, 2, 3
    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=week&period_value=5")
    assert response.status_code == 400
    assert "Invalid week duration" in response.json()["detail"]

    # Month supports only 1, 2, 3, 4
    response = client.get("/api/v1/weather/statistics?city=Indore&period_type=month&period_value=6")
    assert response.status_code == 400
    assert "Invalid month duration" in response.json()["detail"]


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
