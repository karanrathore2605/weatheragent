"""Unit tests for weather and forecast Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.weather_schema import (
    ForecastDay,
    ForecastResponse,
    WeatherErrorResponse,
    WeatherResponse,
)


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
        )


def test_forecast_day_schema_valid() -> None:
    """Test valid instantiation of ForecastDay."""
    day = ForecastDay(
        date="2026-10-02",
        temperature_min=24.5,
        temperature_max=32.1,
        condition="Sunny",
        precipitation_probability=20,
        humidity=60,
        wind_speed=12.4,
    )
    assert day.date == "2026-10-02"
    assert day.temperature_min == 24.5
    assert day.temperature_max == 32.1
    assert day.condition == "Sunny"
    assert day.precipitation_probability == 20
    assert day.humidity == 60
    assert day.wind_speed == 12.4


def test_forecast_response_valid() -> None:
    """Test valid instantiation of ForecastResponse."""
    response = ForecastResponse(
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
        resolved_address="Indore, Madhya Pradesh, India",
    )
    assert response.city == "Indore"
    assert len(response.forecast) == 1
    assert response.forecast[0].date == "2026-10-02"
    assert response.resolved_address == "Indore, Madhya Pradesh, India"


def test_weather_error_response() -> None:
    """Test standard error response schema."""
    error = WeatherErrorResponse(detail="City 'InvalidCity' not found.")
    assert error.detail == "City 'InvalidCity' not found."
