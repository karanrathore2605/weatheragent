"""Statistics schemas re-exported for modularity."""

from app.schemas.weather_schema import (
    CoverageInfo,
    MonthlyAverage,
    StatisticsMetrics,
    StatisticsPeriod,
    WeatherStatisticsRequest,
    WeatherStatisticsResponse,
)

__all__ = [
    "CoverageInfo",
    "MonthlyAverage",
    "StatisticsMetrics",
    "StatisticsPeriod",
    "WeatherStatisticsRequest",
    "WeatherStatisticsResponse",
]
