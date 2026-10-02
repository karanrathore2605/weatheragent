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


from enum import Enum


class StatisticsPeriod(str, Enum):
    """Supported time horizons for weather statistics aggregation."""

    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class WeatherStatisticsRequest(BaseModel):
    """Validation schema for weather statistics query parameters."""

    city: str = Field(..., min_length=1, description="Target city name", examples=["Indore"])
    period: StatisticsPeriod = Field(
        default=StatisticsPeriod.WEEK,
        description="Aggregation time horizon ('week', 'month', 'year')",
        examples=[StatisticsPeriod.WEEK],
    )


class WeatherStatisticsResponse(BaseModel):
    """Structured response payload for weather statistics."""

    status: str = Field("success", description="Status ('success' or 'insufficient_data')", examples=["success"])
    city: str = Field(..., description="Target city name", examples=["Indore"])
    period: str = Field(..., description="Statistical aggregation period ('week', 'month', 'year')", examples=["week"])
    start_date: str = Field(..., description="Start date of aggregation window in YYYY-MM-DD format", examples=["2026-09-28"])
    end_date: str = Field(..., description="End date of aggregation window in YYYY-MM-DD format", examples=["2026-10-04"])
    average_temperature: Optional[float] = Field(None, description="Average temperature in Celsius", examples=[28.4])
    minimum_temperature: Optional[float] = Field(None, description="Minimum temperature in Celsius", examples=[23.1])
    maximum_temperature: Optional[float] = Field(None, description="Maximum temperature in Celsius", examples=[33.7])
    average_feels_like_temperature: Optional[float] = Field(None, description="Average perceived temperature in Celsius", examples=[30.1])
    average_humidity: Optional[float] = Field(None, description="Average relative humidity percentage", examples=[61.2])
    average_wind_speed: Optional[float] = Field(None, description="Average wind speed in km/h", examples=[11.8])
    total_precipitation: Optional[float] = Field(None, description="Total precipitation in mm", examples=[12.4])
    observation_count: int = Field(..., description="Total observations used in calculation", examples=[96])
    coverage_percent: float = Field(..., description="Data coverage percentage for the requested period", examples=[80.0])
    available_from: Optional[str] = Field(None, description="Earliest available observation date if insufficient data", examples=["2026-09-30"])
    available_to: Optional[str] = Field(None, description="Latest available observation date if insufficient data", examples=["2026-10-02"])
    message: Optional[str] = Field(None, description="Status or guidance message", examples=["Not enough historical weather data is available for the requested period."])
