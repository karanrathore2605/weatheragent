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
    cloud_cover: Optional[int] = Field(None, description="Cloud cover percentage (0-100)", examples=[18])
    uv_index: Optional[float] = Field(None, description="UV index level", examples=[1.8])
    visibility: Optional[float] = Field(None, description="Visibility in km", examples=[19.0])
    precipitation: Optional[float] = Field(None, description="Precipitation amount in mm", examples=[0.0])
    summary: Optional[str] = Field(None, description="AI-generated professional meteorological summary", examples=["Indore is currently experiencing clear weather..."])
    summary_status: Optional[str] = Field("SUCCESS", description="Summary generation status ('SUCCESS' or 'UNAVAILABLE')", examples=["SUCCESS"])
    summary_message: Optional[str] = Field(None, description="Status/fallback message if summary generation fails", examples=["Weather summary is currently unavailable."])


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
        description="Period duration value (1-3 for week; 1-12 for month)",
        examples=[1],
    )
    period_value: Optional[int] = Field(
        default=None,
        description="Legacy alias for duration",
        examples=[1],
    )


class MonthlyAverage(BaseModel):
    """Monthly historical temperature metrics."""

    month: str = Field(..., description="Month name (e.g. 'June')", examples=["June"])
    year: int = Field(..., description="Year number (e.g. 2026)", examples=[2026])
    average_temperature_celsius: Optional[float] = Field(None, description="Average temperature in Celsius for this month", examples=[27.8])
    observation_days: int = Field(..., description="Number of valid daily observations in this month", examples=[30])
    total_days: Optional[int] = Field(None, description="Total days in this calendar month", examples=[30])
    coverage_percentage: Optional[float] = Field(None, description="Data coverage percentage for this month", examples=[100.0])
    start_date: Optional[str] = Field(None, description="Start date of this calendar month", examples=["2026-06-01"])
    end_date: Optional[str] = Field(None, description="End date of this calendar month", examples=["2026-06-30"])


class DailyRecord(BaseModel):
    """Daily historical temperature observation record for week analysis."""

    date: str = Field(..., description="Observation date (YYYY-MM-DD)", examples=["2026-09-19"])
    formatted_date: Optional[str] = Field(None, description="Formatted display date (e.g. 'Sep 19')", examples=["Sep 19"])
    average_temperature_celsius: Optional[float] = Field(None, description="Average daily temperature in Celsius", examples=[27.1])
    coverage_percentage: Optional[float] = Field(None, description="Observation data coverage percentage for this day", examples=[100.0])
    status: str = Field("100%", description="Observation status or coverage string ('100%', 'Missing', 'Partial')", examples=["100%"])


class WeatherStatisticsResponse(BaseModel):
    """Structured response payload for weather statistics with monthly breakdown."""

    city: str = Field(..., description="Target city name", examples=["Mumbai"])
    provider: str = Field("Open-Meteo", description="Weather data provider identifier", examples=["Open-Meteo"])
    period_type: str = Field("month", description="Statistical aggregation period ('week' or 'month')", examples=["month"])
    duration: int = Field(1, description="Period duration value (1-3 for week; 1-12 for month)", examples=[5])
    period_value: int = Field(1, description="Period duration value alias", examples=[5])
    start_date: Optional[str] = Field(None, description="Start date of aggregation window in YYYY-MM-DD format", examples=["2026-06-01"])
    end_date: Optional[str] = Field(None, description="End date of aggregation window in YYYY-MM-DD format", examples=["2026-10-31"])

    # Monthly breakdown for multi-month requests
    monthly_averages: Optional[List[MonthlyAverage]] = Field(None, description="Month-by-month temperature breakdown for multi-month periods")

    # Daily breakdown for week requests
    daily_records: Optional[List[DailyRecord]] = Field(None, description="Day-by-day temperature breakdown for week analysis periods")
    daily_breakdown: Optional[List[DailyRecord]] = Field(None, description="Alias for daily_records")

    # Overall temperature metrics
    overall_average_temperature_celsius: Optional[float] = Field(None, description="Overall average temperature in Celsius across the complete period", examples=[28.36])
    average_temperature_celsius: Optional[float] = Field(None, description="Average temperature in Celsius alias", examples=[28.36])

    # Observation day metrics
    total_observation_days: Optional[int] = Field(None, description="Total valid daily observations across all months", examples=[153])
    observation_days: Optional[int] = Field(None, description="Observation days alias", examples=[153])

    # Coverage metrics
    data_coverage_percentage: Optional[float] = Field(None, description="Overall data coverage percentage", examples=[100.0])
    coverage_percentage: Optional[float] = Field(None, description="Coverage percentage alias", examples=[100.0])
    data_coverage: Optional[Dict[str, Any]] = Field(default_factory=lambda: {"complete": True}, description="Data coverage details")
    data_source: str = Field("Open-Meteo", description="Weather data source identifier", examples=["Open-Meteo"])
    coverage: CoverageInfo = Field(default_factory=lambda: CoverageInfo(complete=True), description="Coverage assessment details")
    statistics: Optional[StatisticsMetrics] = Field(None, description="Calculated meteorological statistics")
    status: str = Field("SUCCESS", description="Operation status ('SUCCESS' or 'INSUFFICIENT_HISTORICAL_DATA')", examples=["SUCCESS"])
    message: Optional[str] = Field(None, description="Status or guidance message", examples=["Unable to retrieve historical weather data right now. Please try again."])

    # Backward compatibility convenience fields
    period: Optional[str] = Field(None, description="Legacy period alias", examples=["month"])
    average_temperature: Optional[float] = Field(None, description="Average temperature in Celsius alias", examples=[28.36])
    minimum_temperature: Optional[float] = Field(None, description="Minimum temperature in Celsius", examples=[27.1])
    maximum_temperature: Optional[float] = Field(None, description="Maximum temperature in Celsius", examples=[38.2])
    average_feels_like_temperature: Optional[float] = Field(None, description="Average perceived temperature in Celsius", examples=[34.0])
    average_humidity: Optional[float] = Field(None, description="Average relative humidity percentage", examples=[58.5])
    average_wind_speed: Optional[float] = Field(None, description="Average wind speed in km/h", examples=[12.3])
    total_precipitation: Optional[float] = Field(None, description="Total precipitation in mm", examples=[5.2])
    observation_count: Optional[int] = Field(None, description="Total observations used in calculation", examples=[153])
    available_from: Optional[str] = Field(None, description="Earliest available observation date if insufficient data", examples=["2026-06-01"])
    available_to: Optional[str] = Field(None, description="Latest available observation date if insufficient data", examples=["2026-10-31"])

    # LLM-generated meteorological narrative
    summary: Optional[str] = Field(None, description="Natural language summary generated by Groq LLM", examples=["Over the past 2 weeks in Indore, temperatures averaged 27.2°C..."])


class WeatherSummaryResponse(BaseModel):
    """Structured response payload containing calculated statistics and natural language summary."""

    status: str = Field("SUCCESS", description="Operation status ('SUCCESS', 'PARTIAL_SUCCESS', or 'INSUFFICIENT_HISTORICAL_DATA')", examples=["SUCCESS"])
    city: str = Field(..., description="Target city name", examples=["Indore"])
    period_type: str = Field("week", description="Aggregation period ('week', 'month')", examples=["week"])
    duration: int = Field(1, description="Period duration count", examples=[2])
    statistics: Optional[WeatherStatisticsResponse] = Field(None, description="Deterministic calculated historical weather statistics")
    summary: Optional[str] = Field(None, description="Natural language summary generated by Groq LLM", examples=["Over the past 2 weeks in Indore, temperatures averaged 27.2°C..."])
    message: Optional[str] = Field(None, description="Status or guidance message", examples=[None])



