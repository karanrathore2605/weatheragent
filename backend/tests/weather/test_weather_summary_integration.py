"""Integration tests for weather statistics and AI summary endpoint."""

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
from app.schemas.weather_schema import (
    CoverageInfo,
    DailyRecord,
    MonthlyAverage,
    WeatherStatisticsResponse,
    WeatherSummaryResponse,
)
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


def test_weather_summary_endpoint_success(client: TestClient, mock_stats_service: MagicMock):
    """Test successful summary generation with complete statistics and natural-language narrative."""
    stats_data = WeatherStatisticsResponse(
        status="SUCCESS",
        city="Indore",
        provider="open-meteo",
        period_type="week",
        duration=2,
        period_value=2,
        start_date="2026-09-19",
        end_date="2026-10-03",
        overall_average_temperature_celsius=27.4,
        average_temperature_celsius=27.4,
        observation_days=14,
        data_coverage_percentage=100.0,
        coverage_percentage=100.0,
        daily_records=[
            DailyRecord(date="2026-09-19", average_temperature_celsius=27.0, status="Available", coverage_percentage=100.0),
            DailyRecord(date="2026-09-20", average_temperature_celsius=27.8, status="Available", coverage_percentage=100.0),
        ],
        summary="Over the past 2 weeks in Indore, temperatures averaged a mild 27.4°C with dry conditions.",
    )

    mock_stats_service.get_weather_summary.return_value = WeatherSummaryResponse(
        status="SUCCESS",
        city="Indore",
        period_type="week",
        duration=2,
        statistics=stats_data,
        summary="Over the past 2 weeks in Indore, temperatures averaged a mild 27.4°C with dry conditions.",
        message=None,
    )

    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=week&duration=2")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "SUCCESS"
    assert data["city"] == "Indore"
    assert data["period_type"] == "week"
    assert data["duration"] == 2
    assert "mild 27.4°C" in data["summary"]
    assert data["statistics"]["overall_average_temperature_celsius"] == 27.4
    assert len(data["statistics"]["daily_records"]) == 2


def test_weather_summary_endpoint_partial_success(client: TestClient, mock_stats_service: MagicMock):
    """Test partial success when LLM fails or is unconfigured, leaving deterministic metrics intact."""
    stats_data = WeatherStatisticsResponse(
        status="SUCCESS",
        city="Bhopal",
        provider="open-meteo",
        period_type="month",
        duration=3,
        period_value=3,
        start_date="2026-07-01",
        end_date="2026-09-30",
        overall_average_temperature_celsius=26.5,
        average_temperature_celsius=26.5,
        observation_days=92,
        data_coverage_percentage=100.0,
        monthly_averages=[
            MonthlyAverage(month="July 2026", year=2026, average_temperature_celsius=27.0, coverage_percentage=100.0, observation_days=31),
            MonthlyAverage(month="August 2026", year=2026, average_temperature_celsius=26.2, coverage_percentage=100.0, observation_days=31),
            MonthlyAverage(month="September 2026", year=2026, average_temperature_celsius=26.3, coverage_percentage=100.0, observation_days=30),
        ],
        summary=None,
    )

    mock_stats_service.get_weather_summary.return_value = WeatherSummaryResponse(
        status="PARTIAL_SUCCESS",
        city="Bhopal",
        period_type="month",
        duration=3,
        statistics=stats_data,
        summary=None,
        message="Weather statistics are available, but the AI summary could not be generated right now.",
    )

    response = client.get("/api/v1/weather/statistics/summary?city=Bhopal&period_type=month&duration=3")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "PARTIAL_SUCCESS"
    assert data["summary"] is None
    assert data["statistics"]["overall_average_temperature_celsius"] == 26.5
    assert len(data["statistics"]["monthly_averages"]) == 3
    assert "AI summary could not be generated" in data["message"]


def test_weather_summary_endpoint_insufficient_data(client: TestClient, mock_stats_service: MagicMock):
    """Test handling when historical data is insufficient."""
    mock_stats_service.get_weather_summary.return_value = WeatherSummaryResponse(
        status="INSUFFICIENT_HISTORICAL_DATA",
        city="Indore",
        period_type="month",
        duration=12,
        statistics=WeatherStatisticsResponse(
            status="INSUFFICIENT_HISTORICAL_DATA",
            city="Indore",
            period_type="month",
            duration=12,
            message="Data coverage for selected period is below threshold.",
        ),
        summary=None,
        message="Unable to retrieve historical weather data right now. Please try again.",
    )

    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=month&duration=12")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "INSUFFICIENT_HISTORICAL_DATA"
    assert data["summary"] is None


def test_weather_summary_endpoint_invalid_duration(client: TestClient):
    """Test 400 validation error when duration is invalid for week (e.g. 4 weeks)."""
    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=week&duration=4")
    assert response.status_code == 400
    assert "Invalid week duration: 4" in response.json()["detail"]


def test_weather_summary_endpoint_invalid_month_duration(client: TestClient):
    """Test 400 validation error when duration is invalid for month (e.g. 13 months)."""
    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=month&duration=13")
    assert response.status_code == 400
    assert "Invalid month duration: 13" in response.json()["detail"]


def test_weather_summary_endpoint_invalid_period(client: TestClient):
    """Test 400 validation error when period is 'year' or invalid."""
    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=year&duration=1")
    assert response.status_code == 400
    assert "year" in response.json()["detail"].lower()


def test_weather_summary_endpoint_city_not_found(client: TestClient, mock_stats_service: MagicMock):
    """Test 404 when city is not recognized."""
    mock_stats_service.get_weather_summary.side_effect = CityNotFoundError("City 'Nonexistentxyz' was not found.")

    response = client.get("/api/v1/weather/statistics/summary?city=Nonexistentxyz&period_type=week&duration=1")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_weather_summary_endpoint_provider_timeout(client: TestClient, mock_stats_service: MagicMock):
    """Test 504 when weather provider times out."""
    mock_stats_service.get_weather_summary.side_effect = WeatherTimeoutError("Timeout reaching weather provider")

    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period_type=week&duration=1")
    assert response.status_code == 504
