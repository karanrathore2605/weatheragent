"""Pydantic schemas for Weather endpoints and domain models."""

from typing import Any, Dict, List, Optional
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


class CoverageInfo(BaseModel):
    """Detailed observation coverage assessment."""

    requested: Optional[str] = Field(None, description="Requested coverage description", examples=["1 Week (7 days / 168 hours)"])
    available: Optional[str] = Field(None, description="Available coverage description", examples=["168 hours (100.0%)"])
    complete: bool = Field(..., description="Whether historical coverage is complete/sufficient", examples=[True])
    percent: Optional[float] = Field(None, description="Percentage of required observations available", examples=[100.0])
    observation_count: Optional[int] = Field(None, description="Number of valid observations", examples=[168])


class StatisticsMetrics(BaseModel):
    """Deterministic meteorological statistics metrics."""

    average_temperature: Optional[float] = Field(None, description="Average temperature in Celsius", examples=[32.4])
    minimum_temperature: Optional[float] = Field(None, description="Minimum temperature in Celsius", examples=[27.1])
    maximum_temperature: Optional[float] = Field(None, description="Maximum temperature in Celsius", examples=[38.2])
    average_feels_like_temperature: Optional[float] = Field(None, description="Average perceived temperature in Celsius", examples=[34.0])
    average_humidity: Optional[float] = Field(None, description="Average relative humidity percentage", examples=[58.5])
    average_wind_speed: Optional[float] = Field(None, description="Average wind speed in km/h", examples=[12.3])
    total_precipitation: Optional[float] = Field(0.0, description="Total precipitation in mm", examples=[5.2])


class WeatherStatisticsRequest(BaseModel):
    """Validation schema for weather statistics query parameters."""

    city: str = Field(..., min_length=1, description="Target city name", examples=["Indore"])
    period_type: StatisticsPeriod = Field(
        default=StatisticsPeriod.WEEK,
        description="Aggregation time horizon ('week', 'month')",
        examples=[StatisticsPeriod.WEEK],
    )
    duration: int = Field(
        default=1,
        ge=1,
        le=12,
        description="Period duration value (1-4 for week; 1-12 for month)",
        examples=[1],
    )
    period_value: Optional[int] = Field(
        default=None,
        description="Legacy alias for duration",
        examples=[1],
    )


class WeatherStatisticsResponse(BaseModel):
    """Structured response payload for weather statistics."""

    city: str = Field(..., description="Target city name", examples=["Indore"])
    provider: str = Field("open-meteo", description="Weather data provider identifier", examples=["open-meteo"])
    period_type: str = Field("week", description="Statistical aggregation period ('week' or 'month')", examples=["week"])
    duration: int = Field(1, description="Period duration value (1-4 for week; 1-12 for month)", examples=[1])
    period_value: int = Field(1, description="Period duration value alias", examples=[1])
    start_date: Optional[str] = Field(None, description="Start date of aggregation window in YYYY-MM-DD format", examples=["2026-07-02"])
    end_date: Optional[str] = Field(None, description="End date of aggregation window in YYYY-MM-DD format", examples=["2026-10-02"])
    average_temperature_celsius: Optional[float] = Field(None, description="Average temperature in Celsius", examples=[29.8])
    observation_days: Optional[int] = Field(None, description="Number of valid daily observations used", examples=[92])
    coverage_percentage: Optional[float] = Field(None, description="Data coverage percentage for the requested period", examples=[100.0])
    data_coverage: Optional[Dict[str, Any]] = Field(default_factory=lambda: {"complete": True}, description="Data coverage details")
    data_source: str = Field("open-meteo", description="Weather data source identifier", examples=["open-meteo"])
    coverage: CoverageInfo = Field(default_factory=lambda: CoverageInfo(complete=True), description="Coverage assessment details")
    statistics: Optional[StatisticsMetrics] = Field(None, description="Calculated meteorological statistics")
    status: str = Field("SUCCESS", description="Operation status ('SUCCESS' or 'INSUFFICIENT_HISTORICAL_DATA')", examples=["SUCCESS"])
    message: Optional[str] = Field(None, description="Status or guidance message", examples=["Unable to retrieve historical weather data right now. Please try again."])

    # Backward compatibility convenience fields
    period: Optional[str] = Field(None, description="Legacy period alias", examples=["week"])
    average_temperature: Optional[float] = Field(None, description="Average temperature in Celsius alias", examples=[31.8])
    minimum_temperature: Optional[float] = Field(None, description="Minimum temperature in Celsius", examples=[27.1])
    maximum_temperature: Optional[float] = Field(None, description="Maximum temperature in Celsius", examples=[38.2])
    average_feels_like_temperature: Optional[float] = Field(None, description="Average perceived temperature in Celsius", examples=[34.0])
    average_humidity: Optional[float] = Field(None, description="Average relative humidity percentage", examples=[58.5])
    average_wind_speed: Optional[float] = Field(None, description="Average wind speed in km/h", examples=[12.3])
    total_precipitation: Optional[float] = Field(None, description="Total precipitation in mm", examples=[5.2])
    observation_count: Optional[int] = Field(None, description="Total observations used in calculation", examples=[168])
    coverage_percent: Optional[float] = Field(None, description="Data coverage percentage for the requested period", examples=[100.0])
    available_from: Optional[str] = Field(None, description="Earliest available observation date if insufficient data", examples=["2026-09-25"])
    available_to: Optional[str] = Field(None, description="Latest available observation date if insufficient data", examples=["2026-10-02"])


