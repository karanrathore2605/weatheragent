"""Integration tests verifying persistent weather observations storage during current weather retrieval."""

from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clients.weather_client import GoogleWeatherClient
from app.database.session import Base
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.services.weather_service import WeatherService


@pytest.fixture
def in_memory_repo() -> WeatherObservationRepository:
    """Fixture providing repository backed by in-memory SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return WeatherObservationRepository(session)


@pytest.fixture
def mock_weather_client() -> MagicMock:
    """Fixture providing mocked GoogleWeatherClient."""
    client = MagicMock(spec=GoogleWeatherClient)
    client.geocode_city.return_value = {
        "latitude": 22.7196,
        "longitude": 75.8577,
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    client.get_current_conditions.return_value = {
        "currentTime": "2026-10-02T10:00:00Z",
        "temperature": {"degrees": 28.5},
        "feelsLikeTemperature": {"degrees": 30.0},
        "relativeHumidity": 60,
        "wind": {"speed": {"value": 11.5}},
        "precipitation": {"amount": 0.5},
        "pressure": {"value": 1013.2},
        "weatherCondition": {"description": {"text": "Sunny"}},
    }
    return client


def test_get_current_weather_persists_observation(
    mock_weather_client: MagicMock, in_memory_repo: WeatherObservationRepository
) -> None:
    """Test that a successful get_current_weather call persists an observation in repository."""
    service = WeatherService(client=mock_weather_client, repository=in_memory_repo)

    res = service.get_current_weather("Indore")

    assert res.city == "Indore"
    assert res.temperature == 28.5

    # Verify repository has stored the observation
    assert in_memory_repo.count_observations("Indore") == 1
    stored = in_memory_repo.get_observations_by_city("Indore")
    assert len(stored) == 1
    assert stored[0].temperature == 28.5
    assert stored[0].humidity == 60.0
    assert stored[0].precipitation == 0.5
    assert stored[0].wind_speed == 11.5
    assert stored[0].weather_condition == "Sunny"


def test_get_current_weather_deduplication(
    mock_weather_client: MagicMock, in_memory_repo: WeatherObservationRepository
) -> None:
    """Test that consecutive queries within same observation timestamp do not duplicate rows."""
    service = WeatherService(client=mock_weather_client, repository=in_memory_repo)

    service.get_current_weather("Indore")
    service.get_current_weather("Indore")
    service.get_current_weather("indore")

    # Still exactly 1 observation
    assert in_memory_repo.count_observations("Indore") == 1


def test_get_current_weather_repository_failure_does_not_break_endpoint(
    mock_weather_client: MagicMock,
) -> None:
    """Test that database failure in repository does NOT crash get_current_weather."""
    failing_repo = MagicMock(spec=WeatherObservationRepository)
    failing_repo.save_observation.side_effect = RuntimeError("Database offline")

    service = WeatherService(client=mock_weather_client, repository=failing_repo)

    # Must succeed without throwing
    res = service.get_current_weather("Indore")
    assert res.city == "Indore"
    assert res.temperature == 28.5
