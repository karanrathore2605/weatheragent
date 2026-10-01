"""Schemas layer: Contains Pydantic models for request/response validation.

Architecture Rule:
- Schemas define the contract between client and API (DTOs).
- Schemas are kept strictly separated from database models.
"""

from app.schemas.health import HealthResponse
from app.schemas.weather_schema import (
    ForecastDay,
    ForecastResponse,
    WeatherErrorResponse,
    WeatherResponse,
)

__all__ = [
    "HealthResponse",
    "WeatherResponse",
    "ForecastDay",
    "ForecastResponse",
    "WeatherErrorResponse",
]
