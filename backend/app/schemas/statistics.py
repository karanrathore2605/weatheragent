"""Statistics schemas re-exported for modularity."""

from app.schemas.weather_schema import (
    CoverageInfo,
    StatisticsMetrics,
    StatisticsPeriod,
    WeatherStatisticsRequest,
    WeatherStatisticsResponse,
)

__all__ = [
    "CoverageInfo",
    "StatisticsMetrics",
    "StatisticsPeriod",
    "WeatherStatisticsRequest",
    "WeatherStatisticsResponse",
]
