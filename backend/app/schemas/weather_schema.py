"""Pydantic schemas for Weather endpoints and domain models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class WeatherResponse(BaseModel):
    """Canonical current weather response model."""

    city: str = Field(..., description="Name of the requested or resolved city", examples=["Indore"])
    temperature: float = Field(..., description="Current temperature in degrees Celsius", examples=[28.4])
    feels_like: float = Field(..., description="Perceived temperature in degrees Celsius", examples=[30.1])
    humidity: int = Field(..., description="Relative humidity percentage (0-100)", examples=[65])
    wind_speed: float = Field(..., description="Wind speed in km/h", examples=[12.2])
    condition: str = Field(..., description="Textual description of weather condition", examples=["Partly Cloudy"])
    observed_at: str = Field(..., description="ISO 8601 observation timestamp", examples=["2026-10-01T10:30:00"])
    resolved_address: Optional[str] = Field(None, description="Full geocoded location address", examples=["Indore, Madhya Pradesh, India"])


class ForecastDay(BaseModel):
    """Daily forecast metrics model."""

    date: str = Field(..., description="Forecast date in YYYY-MM-DD format", examples=["2026-10-02"])
    temperature_min: float = Field(..., description="Minimum daily temperature in Celsius", examples=[24.5])
    temperature_max: float = Field(..., description="Maximum daily temperature in Celsius", examples=[32.1])
    condition: str = Field(..., description="Predominant daytime condition description", examples=["Sunny"])
    precipitation_probability: int = Field(..., description="Precipitation probability percentage (0-100)", examples=[20])
    humidity: int = Field(..., description="Relative humidity percentage (0-100)", examples=[60])
    wind_speed: float = Field(..., description="Average wind speed in km/h", examples=[12.4])


class ForecastResponse(BaseModel):
    """Canonical multi-day weather forecast response model."""

    city: str = Field(..., description="Resolved city name", examples=["Indore"])
    forecast: List[ForecastDay] = Field(..., description="Chronological list of daily forecast metrics")
    resolved_address: Optional[str] = Field(None, description="Full geocoded location address", examples=["Indore, Madhya Pradesh, India"])


class WeatherErrorResponse(BaseModel):
    """Standard error response payload."""

    detail: str = Field(..., description="Human-readable error description")
