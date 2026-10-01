"""Unit tests for WeatherService domain logic and normalization."""

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
