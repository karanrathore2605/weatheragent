"""Unit tests for HistoricalWeatherService with mocked Google Weather API."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import (
    CityNotFoundError,
    GoogleWeatherClient,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.services.historical_weather_service import HistoricalWeatherService


@pytest.fixture
def mock_google_client() -> MagicMock:
    """Fixture providing a mocked GoogleWeatherClient."""
    client = MagicMock(spec=GoogleWeatherClient)
    client.geocode_city.return_value = {
        "latitude": 22.7196,
        "longitude": 75.8577,
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    client.get_historical_hours.return_value = {
        "historyHours": [
            {
                "interval": {"startTime": f"2026-10-02T{i:02d}:00:00Z"},
                "temperature": {"degrees": 25.0 + i},
                "feelsLikeTemperature": {"degrees": 26.0 + i},
                "relativeHumidity": 55,
                "wind": {"speed": {"value": 10.0}},
                "precipitation": {"amount": 0.0},
                "weatherCondition": {"description": {"text": "Clear"}},
            }
            for i in range(24)
        ]
    }
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
    mock_google_client: MagicMock, mock_repository: MagicMock
) -> HistoricalWeatherService:
    """Fixture providing HistoricalWeatherService with mocked dependencies."""
    return HistoricalWeatherService(
        client=mock_google_client,
        repository=mock_repository,
        fallback_client=None,
    )


def test_fetch_and_get_observations_calls_google_api(
    historical_service: HistoricalWeatherService,
    mock_google_client: MagicMock,
    mock_repository: MagicMock,
) -> None:
    """Test that Google Weather API is the primary source called with proper parameters."""
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)

    # Verifies Google client was called for geocoding and history
    mock_google_client.geocode_city.assert_called_once_with("Indore")
    mock_google_client.get_historical_hours.assert_called_once_with(
        latitude=22.7196,
        longitude=75.8577,
        hours=24,
    )
    # Verifies observations were saved to repository cache
    assert mock_repository.save_observation.call_count == 24
    mock_repository.get_observations_by_date_range.assert_called_once_with(
        city="Indore",
        start_date=start_dt,
        end_date=end_dt,
    )


def test_google_api_timeout(historical_service: HistoricalWeatherService, mock_google_client: MagicMock) -> None:
    """Test handling of Google Weather API timeout."""
    mock_google_client.get_historical_hours.side_effect = WeatherTimeoutError("Request timed out.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherTimeoutError, match="Request timed out"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)


def test_google_api_auth_failure(historical_service: HistoricalWeatherService, mock_google_client: MagicMock) -> None:
    """Test handling of Google Weather API authentication error."""
    mock_google_client.get_historical_hours.side_effect = WeatherAuthenticationError("Invalid API key.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherAuthenticationError, match="Invalid API key"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)


def test_google_api_invalid_city(historical_service: HistoricalWeatherService, mock_google_client: MagicMock) -> None:
    """Test handling when city is not found in Google Geocoding API."""
    mock_google_client.geocode_city.side_effect = CityNotFoundError("City 'Nonexistent' not found.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(CityNotFoundError, match="City 'Nonexistent' not found"):
        historical_service.fetch_and_get_observations("Nonexistent", start_dt, end_dt)


def test_google_api_service_unavailable(historical_service: HistoricalWeatherService, mock_google_client: MagicMock) -> None:
    """Test handling when Google Weather API returns service unavailable."""
    mock_google_client.get_historical_hours.side_effect = WeatherServiceUnavailableError("Service unavailable.")
    start_dt = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherServiceUnavailableError, match="Service unavailable"):
        historical_service.fetch_and_get_observations("Indore", start_dt, end_dt)
