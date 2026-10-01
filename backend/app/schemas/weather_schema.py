"""Pydantic schemas for Weather endpoints and domain models."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


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


class WeatherErrorResponse(BaseModel):
    """Standard error response payload."""

    detail: str = Field(..., description="Human-readable error description")
