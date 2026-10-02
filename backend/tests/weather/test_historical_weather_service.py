"""Unit tests for HistoricalWeatherService with mocked AccuWeather API client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from app.clients.accuweather_client import AccuWeatherClient
from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.services.historical_weather_service import HistoricalWeatherService


@pytest.fixture
def mock_accuweather_client() -> MagicMock:
    """Fixture providing a mocked AccuWeatherClient."""
    client = MagicMock(spec=AccuWeatherClient)
    client.search_location.return_value = {
        "key": "202441",
        "city": "Indore",
        "administrative_area": "Madhya Pradesh",
        "country": "India",
        "latitude": 22.7196,
        "longitude": 75.8577,
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    client.get_historical_conditions.return_value = [
        {
            "LocalObservationDateTime": f"2026-10-02T{i:02d}:00:00+05:30",
            "EpochTime": 1790924400 + i * 3600,
            "WeatherText": "Clear",
            "Temperature": {"Metric": {"Value": 25.0 + i, "Unit": "C"}},
            "RealFeelTemperature": {"Metric": {"Value": 26.0 + i, "Unit": "C"}},
            "RelativeHumidity": 55,
        }
        for i in range(24)
    ]
    return client


@pytest.fixture
def mock_repository() -> MagicMock:
    """Fixture providing a mocked WeatherObservationRepository."""
    repo = MagicMock(spec=WeatherObservationRepository)
    repo.get_observations_by_date_range.return_value = []
    repo.check_available_data_range.return_value = (None, None)
    return repo


@pytest.fixture
def historical_service(
    mock_accuweather_client: MagicMock, mock_repository: MagicMock
) -> HistoricalWeatherService:
    """Fixture providing HistoricalWeatherService with mocked dependencies."""
    return HistoricalWeatherService(
        accuweather_client=mock_accuweather_client,
        repository=mock_repository,
    )


def test_fetch_and_get_observations_calls_accuweather_api(
    historical_service: HistoricalWeatherService,
    mock_accuweather_client: MagicMock,
    mock_repository: MagicMock,
) -> None:
    """Test that AccuWeather is the primary source called with proper parameters."""
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)

    # Verifies AccuWeather client was called for location search and historical conditions
    mock_accuweather_client.search_location.assert_called_once_with("Indore")
    mock_accuweather_client.get_historical_conditions.assert_called_once_with(
        location_key="202441",
        hours=24,
    )
    # Verifies observations were saved to repository cache
    assert mock_repository.save_observation.call_count == 24
    mock_repository.get_observations_by_date_range.assert_called_once_with(
        city="Indore",
        start_date=start_dt,
        end_date=end_dt,
    )


def test_accuweather_api_timeout(historical_service: HistoricalWeatherService, mock_accuweather_client: MagicMock) -> None:
    """Test handling of AccuWeather API timeout."""
    mock_accuweather_client.get_historical_conditions.side_effect = WeatherTimeoutError("AccuWeather historical request timed out.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherTimeoutError, match="timed out"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)


def test_accuweather_api_auth_failure(historical_service: HistoricalWeatherService, mock_accuweather_client: MagicMock) -> None:
    """Test handling of AccuWeather API authentication error."""
    mock_accuweather_client.search_location.side_effect = WeatherAuthenticationError("AccuWeather service authentication failed.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherAuthenticationError, match="authentication failed"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)


def test_accuweather_api_invalid_city(historical_service: HistoricalWeatherService, mock_accuweather_client: MagicMock) -> None:
    """Test handling when city is not found in AccuWeather Locations API."""
    mock_accuweather_client.search_location.side_effect = CityNotFoundError("City 'Nonexistent' not found.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(CityNotFoundError, match="City 'Nonexistent' not found"):
        historical_service.fetch_and_get_observations("Nonexistent", start_dt, end_dt)


def test_accuweather_api_service_unavailable(historical_service: HistoricalWeatherService, mock_accuweather_client: MagicMock) -> None:
    """Test handling when AccuWeather returns service unavailable."""
    mock_accuweather_client.get_historical_conditions.side_effect = WeatherServiceUnavailableError("AccuWeather service is temporarily unavailable.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)
