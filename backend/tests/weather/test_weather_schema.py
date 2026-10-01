"""Unit tests for weather Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.weather_schema import WeatherResponse, WeatherErrorResponse


def test_weather_response_valid() -> None:
    """Test valid instantiation and serialization of WeatherResponse."""
    data = {
        "city": "Indore",
        "temperature": 28.4,
        "feels_like": 30.1,
        "humidity": 65,
        "wind_speed": 12.2,
        "condition": "Partly Cloudy",
        "observed_at": "2026-10-01T10:30:00",
    }
    model = WeatherResponse(**data)
    assert model.city == "Indore"
    assert model.temperature == 28.4
    assert model.feels_like == 30.1
    assert model.humidity == 65
    assert model.wind_speed == 12.2
    assert model.condition == "Partly Cloudy"
    assert model.observed_at == "2026-10-01T10:30:00"


def test_weather_response_missing_required_field() -> None:
    """Test validation failure when a required field is missing."""
    with pytest.raises(ValidationError):
        WeatherResponse(
            city="Indore",
            temperature=28.4,
            # missing feels_like, humidity, wind_speed, condition, observed_at
        )


def test_weather_error_response() -> None:
    """Test standard error response schema."""
    error = WeatherErrorResponse(detail="City 'InvalidCity' not found.")
    assert error.detail == "City 'InvalidCity' not found."
