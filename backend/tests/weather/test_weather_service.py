"""Unit tests for WeatherService domain logic and normalization."""

from typing import Any
from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import CityNotFoundError, GoogleWeatherClient, WeatherTimeoutError
from app.schemas.weather_schema import WeatherResponse
from app.services.weather_service import WeatherService


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture providing a mocked GoogleWeatherClient."""
    client = MagicMock(spec=GoogleWeatherClient)
    client.geocode_city.return_value = {
        "latitude": 22.7196,
        "longitude": 75.8577,
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    client.get_current_conditions.return_value = {
        "currentTime": "2026-10-01T10:30:00Z",
        "temperature": {"degrees": 28.4},
        "feelsLikeTemperature": {"degrees": 30.1},
        "relativeHumidity": 65,
        "wind": {"speed": {"value": 12.2}},
        "weatherCondition": {"description": {"text": "Partly Cloudy"}},
    }
    return client


def test_validate_city_input_valid() -> None:
    """Test validation of valid city names."""
    service = WeatherService()
    assert service.validate_city_input("Indore") == "Indore"
    assert service.validate_city_input("  Delhi  ") == "Delhi"
    assert service.validate_city_input("New York") == "New York"


@pytest.mark.parametrize("invalid_city,expected_err", [
    ("", "City name cannot be empty"),
    ("   ", "City name cannot be empty"),
    ("A", "at least 2 characters"),
    ("12345", "contain alphabetic characters"),
    ("!@#$%", "contain alphabetic characters"),
])
def test_validate_city_input_invalid(invalid_city: str, expected_err: str) -> None:
    """Test validation errors on empty or malformed city names."""
    service = WeatherService()
    with pytest.raises(ValueError, match=expected_err):
        service.validate_city_input(invalid_city)


def test_normalize_weather_data_complete() -> None:
    """Test normalization with complete provider response."""
    service = WeatherService()
    location = {
        "latitude": 22.7196,
        "longitude": 75.8577,
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    raw_data = {
        "currentTime": "2026-10-01T10:30:00",
        "temperature": {"degrees": 28.4},
        "feelsLikeTemperature": {"degrees": 30.1},
        "relativeHumidity": 65,
        "wind": {"speed": {"value": 12.2}},
        "weatherCondition": {"description": {"text": "Partly Cloudy"}},
    }

    normalized = service.normalize_weather_data("Indore", location, raw_data)

    assert isinstance(normalized, WeatherResponse)
    assert normalized.city == "Indore"
    assert normalized.temperature == 28.4
    assert normalized.feels_like == 30.1
    assert normalized.humidity == 65
    assert normalized.wind_speed == 12.2
    assert normalized.condition == "Partly Cloudy"
    assert normalized.observed_at == "2026-10-01T10:30:00"
    assert normalized.resolved_address == "Indore, Madhya Pradesh, India"


def test_normalize_weather_data_fallback() -> None:
    """Test normalization when provider data is sparse or partial."""
    service = WeatherService()
    location = {"formatted_address": "Indore"}
    raw_data = {}

    normalized = service.normalize_weather_data("Indore", location, raw_data)

    assert normalized.city == "Indore"
    assert normalized.temperature == 0.0
    assert normalized.feels_like == 0.0
    assert normalized.humidity == 0
    assert normalized.wind_speed == 0.0
    assert normalized.condition == "Clear"
    assert normalized.observed_at is not None


def test_get_current_weather_flow(mock_client: MagicMock) -> None:
    """Test end-to-end execution flow of WeatherService with mocked client."""
    service = WeatherService(client=mock_client)
    response = service.get_current_weather("Indore")

    mock_client.geocode_city.assert_called_once_with("Indore")
    mock_client.get_current_conditions.assert_called_once_with(
        latitude=22.7196,
        longitude=75.8577,
    )

    assert response.city == "Indore"
    assert response.temperature == 28.4
    assert response.condition == "Partly Cloudy"


def test_get_current_weather_city_not_found(mock_client: MagicMock) -> None:
    """Test service propagates CityNotFoundError."""
    mock_client.geocode_city.side_effect = CityNotFoundError("City 'Unknown' not found.")
    service = WeatherService(client=mock_client)

    with pytest.raises(CityNotFoundError):
        service.get_current_weather("Unknown")


def test_get_current_weather_timeout(mock_client: MagicMock) -> None:
    """Test service propagates WeatherTimeoutError."""
    mock_client.get_current_conditions.side_effect = WeatherTimeoutError("Request timed out.")
    service = WeatherService(client=mock_client)

    with pytest.raises(WeatherTimeoutError):
        service.get_current_weather("Indore")


def test_validate_forecast_days_valid() -> None:
    """Test validation of valid forecast days."""
    service = WeatherService()
    assert service.validate_forecast_days(1) == 1
    assert service.validate_forecast_days(5) == 5
    assert service.validate_forecast_days(10) == 10
    assert service.validate_forecast_days("7") == 7


@pytest.mark.parametrize("invalid_days", [0, -1, -5, 11, 20, "abc", None])
def test_validate_forecast_days_invalid(invalid_days: Any) -> None:
    """Test validation errors for out-of-range or non-numeric forecast days."""
    service = WeatherService()
    with pytest.raises(ValueError):
        service.validate_forecast_days(invalid_days)


def test_normalize_forecast_data() -> None:
    """Test normalization of multi-day forecast raw data."""
    service = WeatherService()
    location = {
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    raw_forecast = {
        "forecastDays": [
            {
                "interval": {"startTime": "2026-10-02T00:00:00Z"},
                "daytimeForecast": {
                    "temperature": {"min": 24.5, "max": 32.1},
                    "weatherCondition": {"description": {"text": "Sunny"}},
                    "precipitation": {"probability": 0.20},
                    "humidity": {"relative": 60},
                    "wind": {"speed": {"value": 12.4}},
                },
            },
            {
                "interval": {"startTime": "2026-10-03T00:00:00Z"},
                "daytimeForecast": {
                    "temperature": {"min": 23.0, "max": 31.0},
                    "weatherCondition": {"description": {"text": "Partly Cloudy"}},
                    "precipitation": {"probability": 15},
                    "humidity": {"relative": 65},
                    "wind": {"speed": {"value": 10.0}},
                },
            },
        ]
    }

    result = service.normalize_forecast_data("Indore", location, raw_forecast, requested_days=2)
    assert result.city == "Indore"
    assert len(result.forecast) == 2

    day1 = result.forecast[0]
    assert day1.date == "2026-10-02"
    assert day1.temperature_min == 24.5
    assert day1.temperature_max == 32.1
    assert day1.condition == "Sunny"
    assert day1.precipitation_probability == 20
    assert day1.humidity == 60
    assert day1.wind_speed == 12.4

    day2 = result.forecast[1]
    assert day2.date == "2026-10-03"
    assert day2.precipitation_probability == 15


def test_get_forecast_flow(mock_client: MagicMock) -> None:
    """Test full get_forecast execution flow."""
    mock_client.get_forecast.return_value = {
        "forecastDays": [
            {
                "interval": {"startTime": "2026-10-02T00:00:00Z"},
                "daytimeForecast": {
                    "temperature": {"min": 24.5, "max": 32.1},
                    "weatherCondition": {"description": {"text": "Sunny"}},
                    "precipitation": {"probability": 0.20},
                    "humidity": {"relative": 60},
                    "wind": {"speed": {"value": 12.4}},
                },
            }
        ]
    }
    service = WeatherService(client=mock_client)
    result = service.get_forecast("Indore", days=5)

    mock_client.geocode_city.assert_called_with("Indore")
    mock_client.get_forecast.assert_called_with(
        latitude=22.7196,
        longitude=75.8577,
        days=5,
    )
    assert result.city == "Indore"
    assert len(result.forecast) == 1

