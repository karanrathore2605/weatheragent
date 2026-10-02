"""Integration tests for weather statistics HTTP router."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.statistics_router import get_statistics_service
from app.schemas.weather_schema import WeatherStatisticsResponse
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
    """Test successful GET /api/v1/weather/statistics?city=Indore&period=week."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="success",
        city="Indore",
        period="week",
        start_date="2026-09-28",
        end_date="2026-10-04",
        average_temperature=28.4,
        minimum_temperature=23.1,
        maximum_temperature=33.7,
        average_feels_like_temperature=30.1,
        average_humidity=61.2,
        average_wind_speed=11.8,
        total_precipitation=12.4,
        observation_count=130,
        coverage_percent=77.4,
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["city"] == "Indore"
    assert data["period"] == "week"
    assert data["average_temperature"] == 28.4
    assert data["minimum_temperature"] == 23.1
    assert data["maximum_temperature"] == 33.7
    assert data["total_precipitation"] == 12.4
    assert data["coverage_percent"] == 77.4


def test_get_statistics_insufficient_data(client: TestClient, mock_stats_service: MagicMock) -> None:
    """Test GET /api/v1/weather/statistics returning insufficient data payload."""
    mock_stats_service.calculate_average_weather.return_value = WeatherStatisticsResponse(
        status="insufficient_data",
        city="Indore",
        period="year",
        start_date="2026-01-01",
        end_date="2026-12-31",
        observation_count=48,
        coverage_percent=0.5,
        available_from="2026-09-30",
        available_to="2026-10-02",
        message="Not enough historical weather data is available for the requested period.",
    )

    response = client.get("/api/v1/weather/statistics?city=Indore&period=year")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "insufficient_data"
    assert data["city"] == "Indore"
    assert data["coverage_percent"] == 0.5
    assert data["average_temperature"] is None
    assert data["available_from"] == "2026-09-30"
    assert data["available_to"] == "2026-10-02"


def test_get_statistics_invalid_period(client: TestClient) -> None:
    """Test GET /api/v1/weather/statistics with unsupported period fails validation."""
    response = client.get("/api/v1/weather/statistics?city=Indore&period=century")
    assert response.status_code in [400, 422]


def test_get_statistics_missing_city(client: TestClient) -> None:
    """Test GET /api/v1/weather/statistics without city query param."""
    response = client.get("/api/v1/weather/statistics?period=week")
    assert response.status_code == 422


def test_get_statistics_service_validation_error(
    client: TestClient, mock_stats_service: MagicMock
) -> None:
    """Test ValueError raised from service yields HTTP 400."""
    mock_stats_service.calculate_average_weather.side_effect = ValueError("City name cannot be empty.")

    response = client.get("/api/v1/weather/statistics?city=InvalidCity&period=week")
    assert response.status_code == 400
    assert "City name cannot be empty." in response.json()["detail"]


def test_get_statistics_internal_error(
    client: TestClient, mock_stats_service: MagicMock
) -> None:
    """Test unhandled exception yields HTTP 500."""
    mock_stats_service.calculate_average_weather.side_effect = RuntimeError("Database connection lost")

    response = client.get("/api/v1/weather/statistics?city=Indore&period=week")
    assert response.status_code == 500
    assert "An error occurred while calculating weather statistics" in response.json()["detail"]
