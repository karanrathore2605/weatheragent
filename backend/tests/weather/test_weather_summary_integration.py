"""Integration tests for StatisticsService + LLMService and HTTP summary endpoint."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.weather_observation import WeatherObservation
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.routers.statistics_router import get_statistics_service
from app.schemas.weather_schema import (
    StatisticsPeriod,
    WeatherMetrics,
    WeatherSummaryResponse,
)
from app.services.llm_service import LLMService
from app.services.statistics_service import StatisticsService


def create_mock_observation(
    city: str = "Indore",
    dt: datetime = None,
    temp: float = 28.0,
) -> WeatherObservation:
    """Helper creating mock observation records."""
    return WeatherObservation(
        id=1,
        city=city,
        latitude=22.7,
        longitude=75.8,
        observed_at=dt or datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature=temp,
        feels_like_temperature=30.0,
        humidity=60.0,
        precipitation=1.0,
        wind_speed=12.0,
        pressure=1012.0,
        weather_condition="Sunny",
        source="google",
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    """Fixture providing mock WeatherObservationRepository."""
    repo = MagicMock(spec=WeatherObservationRepository)
    repo.check_available_data_range.return_value = (
        datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    return repo


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Fixture providing mock LLMService."""
    service = MagicMock(spec=LLMService)
    service.generate_weather_summary.return_value = (
        "This week in Indore, the average temperature was 28.0°C with sunny conditions."
    )
    return service


@pytest.fixture
def stats_service(mock_repo: MagicMock, mock_llm_service: MagicMock) -> StatisticsService:
    """Fixture providing StatisticsService with mock repo and mock LLM."""
    return StatisticsService(
        repository=mock_repo,
        min_coverage=70.0,
        llm_service=mock_llm_service,
    )


# --- Service Integration Tests ---

def test_summary_sufficient_data_calls_llm(
    stats_service: StatisticsService,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
) -> None:
    """Test that sufficient data generates statistics AND invokes LLM."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    base = datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc)
    # 140 observations out of 168 (83.3% > 70%)
    observations = [
        create_mock_observation(dt=base + timedelta(hours=i), temp=25.0 + (i % 5))
        for i in range(140)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations

    res = stats_service.get_weather_summary("Indore", "week", reference_date=ref)

    assert res.status == "success"
    assert res.city == "Indore"
    assert res.statistics is not None
    assert res.statistics.average_temperature is not None
    assert res.summary == "This week in Indore, the average temperature was 28.0°C with sunny conditions."
    mock_llm_service.generate_weather_summary.assert_called_once()


def test_summary_insufficient_data_never_calls_llm(
    stats_service: StatisticsService,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
) -> None:
    """CRITICAL RULE: If statistics status is insufficient_data, Groq MUST NOT be called."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Only 5 observations (~3% coverage)
    observations = [
        create_mock_observation(dt=datetime(2026, 9, 28, i, 0, 0, tzinfo=timezone.utc))
        for i in range(5)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations

    res = stats_service.get_weather_summary("Indore", "week", reference_date=ref)

    assert res.status == "insufficient_data"
    assert res.statistics is None
    assert res.summary is None
    assert "Not enough historical weather data" in res.message
    # Verify LLM was NOT called
    mock_llm_service.generate_weather_summary.assert_not_called()


def test_summary_llm_failure_returns_partial_success(
    stats_service: StatisticsService,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
) -> None:
    """CRITICAL RULE: LLM failure must NOT destroy calculated statistics (returns partial_success)."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    base = datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc)
    observations = [
        create_mock_observation(dt=base + timedelta(hours=i), temp=28.0)
        for i in range(130)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations

    # Simulate LLM failure (e.g. timeout or exception returning None)
    mock_llm_service.generate_weather_summary.return_value = None

    res = stats_service.get_weather_summary("Indore", "week", reference_date=ref)

    assert res.status == "partial_success"
    assert res.summary is None
    assert res.statistics is not None
    assert res.statistics.average_temperature == 28.0
    assert "Weather statistics are available, but the summary could not be generated" in res.message


@pytest.mark.parametrize("period", ["week", "month", "year"])
def test_summary_all_periods_supported(
    stats_service: StatisticsService,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
    period: str,
) -> None:
    """Test that week, month, and year periods work end-to-end."""
    # Return 10,000 observations to guarantee > 70% coverage for year
    now = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    observations = [
        create_mock_observation(dt=now + timedelta(hours=i), temp=26.0)
        for i in range(9000)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations

    res = stats_service.get_weather_summary("Indore", period, reference_date=now)
    assert res.status == "success"
    assert res.period == period
    assert res.summary is not None


# --- HTTP Endpoint Integration Tests ---

@pytest.fixture
def client(stats_service: StatisticsService) -> TestClient:
    """TestClient fixture overriding get_statistics_service."""
    app.dependency_overrides[get_statistics_service] = lambda: stats_service
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_api_get_statistics_summary_success(
    client: TestClient,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
) -> None:
    """Test GET /api/v1/weather/statistics/summary?city=Indore&period=week success."""
    now = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    observations = [
        create_mock_observation(dt=now + timedelta(hours=i), temp=28.5)
        for i in range(140)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations

    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period=week")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["city"] == "Indore"
    assert data["period"] == "week"
    assert data["statistics"]["average_temperature"] == 28.5
    assert "Indore" in data["summary"]


def test_api_get_statistics_summary_insufficient_data(
    client: TestClient,
    mock_repo: MagicMock,
    mock_llm_service: MagicMock,
) -> None:
    """Test GET /api/v1/weather/statistics/summary returns 200 with insufficient_data."""
    mock_repo.get_observations_by_date_range.return_value = []
    mock_repo.check_available_data_range.return_value = (None, None)

    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period=week")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "insufficient_data"
    assert data["statistics"] is None
    assert data["summary"] is None
    assert "Not enough historical weather data" in data["message"]


def test_api_get_statistics_summary_invalid_city(client: TestClient) -> None:
    """Test validation failure on empty/invalid city parameter."""
    response = client.get("/api/v1/weather/statistics/summary?city=123&period=week")
    assert response.status_code == 400


def test_api_get_statistics_summary_invalid_period(client: TestClient) -> None:
    """Test validation failure on unsupported period parameter."""
    response = client.get("/api/v1/weather/statistics/summary?city=Indore&period=century")
    assert response.status_code in [400, 422]
