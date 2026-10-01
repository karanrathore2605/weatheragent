"""Unit tests for thin weather tools layer."""

from unittest.mock import MagicMock

from app.schemas.weather_schema import WeatherResponse
from app.services.weather_service import WeatherService
from app.tools.weather_tools import get_current_weather


def test_get_current_weather_tool_delegation() -> None:
    """Test that get_current_weather tool delegates cleanly to WeatherService."""
    mock_service = MagicMock(spec=WeatherService)
    mock_service.get_current_weather.return_value = WeatherResponse(
        city="Indore",
        temperature=28.4,
        feels_like=30.1,
        humidity=65,
        wind_speed=12.2,
        condition="Partly Cloudy",
        observed_at="2026-10-01T10:30:00",
    )

    result = get_current_weather("Indore", service=mock_service)

    mock_service.get_current_weather.assert_called_once_with("Indore")
    assert result.city == "Indore"
    assert result.temperature == 28.4
    assert result.condition == "Partly Cloudy"
