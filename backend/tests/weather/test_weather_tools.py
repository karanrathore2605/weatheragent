"""Unit tests for thin weather tools layer."""

from unittest.mock import MagicMock

from app.schemas.weather_schema import ForecastDay, ForecastResponse, WeatherResponse
from app.services.weather_service import WeatherService
from app.tools.weather_tools import get_current_weather, get_weather_forecast


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


def test_get_weather_forecast_tool_delegation() -> None:
    """Test that get_weather_forecast tool delegates cleanly to WeatherService."""
    mock_service = MagicMock(spec=WeatherService)
    mock_service.get_forecast.return_value = ForecastResponse(
        city="Indore",
        forecast=[
            ForecastDay(
                date="2026-10-02",
                temperature_min=24.5,
                temperature_max=32.1,
                condition="Sunny",
                precipitation_probability=20,
                humidity=60,
                wind_speed=12.4,
            )
        ],
    )

    result = get_weather_forecast("Indore", days=5, service=mock_service)

    mock_service.get_forecast.assert_called_once_with(city="Indore", days=5)
    assert result.city == "Indore"
    assert len(result.forecast) == 1
    assert result.forecast[0].date == "2026-10-02"
