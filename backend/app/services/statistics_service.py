"""Statistics service for deterministic AccuWeather meteorological calculations and data sufficiency checks."""

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple, Union

from app.clients.accuweather_client import AccuWeatherClient
from app.config.settings import settings
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import (
    CoverageInfo,
    StatisticsMetrics,
    StatisticsPeriod,
    WeatherStatisticsResponse,
)
from app.services.average_temperature_calculator import AverageTemperatureCalculator
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.statistics_calculator import StatisticsCalculator
from app.utils.logger import get_logger

logger = get_logger(__name__)


def subtract_months(dt: datetime, months: int) -> datetime:
    """Accurately subtract a given number of months from a datetime in UTC."""
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)


class StatisticsService:
    """Production service for computing historical weather statistics using AccuWeather."""

    def __init__(
        self,
        historical_service: Optional[HistoricalWeatherService] = None,
        repository: Optional[WeatherObservationRepository] = None,
        accuweather_client: Optional[AccuWeatherClient] = None,
        client: Optional[Any] = None,
        min_coverage: Optional[float] = None,
        calculator: Optional[StatisticsCalculator] = None,
        temperature_calculator: Optional[AverageTemperatureCalculator] = None,
    ) -> None:
        client_to_use = accuweather_client or client
        if historical_service is not None:
            self.historical_service = historical_service
        else:
            self.historical_service = HistoricalWeatherService(
                accuweather_client=client_to_use,
                repository=repository,
            )
        self.repository = repository or (self.historical_service.repository if self.historical_service else None)
        self.min_coverage = (
            min_coverage if min_coverage is not None else settings.min_statistics_coverage
        )
        self.calculator = calculator or StatisticsCalculator()
        self.temperature_calculator = temperature_calculator or AverageTemperatureCalculator()

    @staticmethod
    def validate_city_input(city: str) -> str:
        """Validate city parameter.
        
        Raises:
            ValueError: If city is empty or lacks alphabetic characters.
        """
        if not city or not city.strip():
            logger.warning("Empty or whitespace-only city parameter provided to StatisticsService")
            raise ValueError("City name cannot be empty.")

        trimmed = city.strip()
        if len(trimmed) < 2:
            logger.warning("City name too short: '%s'", trimmed)
            raise ValueError("City name must be at least 2 characters long.")

        if not re.search(r"[a-zA-Z]", trimmed):
            logger.warning("City name has no alphabetic characters: '%s'", trimmed)
            raise ValueError("City name must contain alphabetic characters.")

        return trimmed.title()

    @staticmethod
    def parse_period(period: Union[StatisticsPeriod, str]) -> StatisticsPeriod:
        """Parse and validate aggregation period string into enum.
        
        Note: The 'year' option has been completely removed.
        
        Raises:
            ValueError: If period is unsupported or if 'year' is requested.
        """
        if isinstance(period, StatisticsPeriod):
            return period
        if not period or not isinstance(period, str):
            raise ValueError("Statistics period is required.")

        normalized = period.strip().lower()
        if normalized == "year":
            raise ValueError("The 'year' period option has been removed. Supported periods: week, month.")

        try:
            return StatisticsPeriod(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid statistics period '{period}'. Supported periods: week, month."
            )

    @staticmethod
    def validate_period_value(period: StatisticsPeriod, period_value: int) -> int:
        """Validate duration integer for the selected period.
        
        Week: 1, 2, 3, 4
        Month: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        """
        try:
            val = int(period_value)
        except (ValueError, TypeError):
            raise ValueError("Period duration must be an integer.")

        if period == StatisticsPeriod.WEEK:
            if val not in (1, 2, 3, 4):
                raise ValueError(
                    f"Invalid week duration: {val}. Supported durations for week: 1, 2, 3, or 4 weeks."
                )
        elif period == StatisticsPeriod.MONTH:
            if val not in tuple(range(1, 13)):
                raise ValueError(
                    f"Invalid month duration: {val}. Supported durations for month: 1 to 12 months."
                )
        return val

    @classmethod
    def get_date_range(
        cls,
        period: Union[StatisticsPeriod, str],
        period_value: Union[int, datetime] = 1,
        reference_date: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime, int]:
        """Compute UTC start and end bounds for the specified calendar period.
        
        Supports:
        - 1-4 Weeks  -> previous 7, 14, 21, 28 calendar days
        - 1-12 Months -> previous 1-12 calendar months
        
        Returns:
            (start_date_utc, end_date_utc, expected_hourly_observations)
        """
        if isinstance(period_value, datetime):
            reference_date = period_value
            period_value = 1

        period_enum = cls.parse_period(period)
        duration = cls.validate_period_value(period_enum, int(period_value))

        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        else:
            ref = ref.astimezone(timezone.utc)

        end_date = ref

        if period_enum == StatisticsPeriod.WEEK:
            days = duration * 7
            start_date = ref - timedelta(days=days)
            expected_observations = days * 24

        elif period_enum == StatisticsPeriod.MONTH:
            start_date = subtract_months(ref, duration)
            days = max(1, (end_date.date() - start_date.date()).days)
            expected_observations = days * 24

        else:
            raise ValueError(f"Unsupported period: {period_enum}")

        return start_date, end_date, expected_observations

    def calculate_average_weather(
        self,
        city: str,
        period: Union[StatisticsPeriod, str] = StatisticsPeriod.WEEK,
        period_value: int = 1,
        duration: Optional[int] = None,
        reference_date: Optional[datetime] = None,
    ) -> WeatherStatisticsResponse:
        """Calculate deterministic AccuWeather historical statistics for a city over a defined duration.
        
        Flow:
        1. Validate city, period, and duration.
        2. Compute timezone-aware date range.
        3. Request historical data via HistoricalWeatherService (AccuWeather).
        4. Validate data coverage against threshold.
        5. If coverage is incomplete, return INSUFFICIENT_HISTORICAL_DATA response without fake numbers.
        6. Compute average temperature via AverageTemperatureCalculator.
        7. Return structured WeatherStatisticsResponse.
        """
        valid_city = self.validate_city_input(city)
        period_enum = self.parse_period(period)
        effective_duration = duration if duration is not None else period_value
        valid_duration = self.validate_period_value(period_enum, effective_duration)

        start_date, end_date, expected_obs = self.get_date_range(
            period=period_enum,
            period_value=valid_duration,
            reference_date=reference_date,
        )

        period_label = f"{valid_duration} {period_enum.value.title() if valid_duration == 1 else period_enum.value.title() + 's'}"
        expected_days = max(1, (end_date.date() - start_date.date()).days)

        logger.info(
            "Computing %s historical statistics for '%s' (%s to %s, expected_hours=%s) via AccuWeather",
            period_label,
            valid_city,
            start_date.isoformat(),
            end_date.isoformat(),
            expected_obs,
        )

        # Retrieve observations from AccuWeather via HistoricalWeatherService
        observations, location = self.historical_service.fetch_and_get_observations(
            city=valid_city,
            start_date=start_date,
            end_date=end_date,
        )

        obs_count = len(observations)
        coverage_percent = round(
            min(100.0, (obs_count / expected_obs) * 100.0) if expected_obs > 0 else 0.0,
            1,
        )

        # Sufficient coverage requires reaching threshold percentage and having observations
        is_complete = (obs_count >= int(expected_obs * (self.min_coverage / 100.0))) and (obs_count > 0)

        # Query available range for guidance if database repository exists
        earliest_str, latest_str = None, None
        if self.repository is not None and hasattr(self.repository, "check_available_data_range"):
            earliest, latest = self.repository.check_available_data_range(valid_city)
            if earliest:
                earliest_str = earliest.strftime("%Y-%m-%d")
            if latest:
                latest_str = latest.strftime("%Y-%m-%d")

        if not is_complete:
            logger.info(
                "Incomplete AccuWeather coverage for '%s' (%s): %d/%d hours (%.1f%% < %.1f%%)",
                valid_city,
                period_label,
                obs_count,
                expected_obs,
                coverage_percent,
                self.min_coverage,
            )
            return WeatherStatisticsResponse(
                city=valid_city,
                provider="accuweather",
                period_type=period_enum.value,
                duration=valid_duration,
                period_value=valid_duration,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                average_temperature_celsius=None,
                data_coverage={"complete": False},
                status="INSUFFICIENT_HISTORICAL_DATA",
                message="Historical weather data is not available for the complete requested period.",
                data_source="accuweather",
                coverage=CoverageInfo(
                    requested=f"{period_label} ({expected_days} days / {expected_obs} hours)",
                    available=f"{obs_count} hours ({coverage_percent}%)",
                    complete=False,
                    percent=coverage_percent,
                    observation_count=obs_count,
                ),
                statistics=None,
                period=period_enum.value,
                average_temperature=None,
                coverage_percent=coverage_percent,
                observation_count=obs_count,
                available_from=earliest_str,
                available_to=latest_str,
            )

        # Calculate average temperature strictly from observations without fabrication
        avg_temp = self.temperature_calculator.calculate_average_temperature(observations)
        metrics = self.calculator.calculate(observations)

        return WeatherStatisticsResponse(
            city=valid_city,
            provider="accuweather",
            period_type=period_enum.value,
            duration=valid_duration,
            period_value=valid_duration,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            average_temperature_celsius=avg_temp,
            data_coverage={"complete": True},
            status="SUCCESS",
            message=None,
            data_source="accuweather",
            coverage=CoverageInfo(
                requested=f"{period_label} ({expected_days} days / {expected_obs} hours)",
                available=f"{obs_count} hours ({coverage_percent}%)",
                complete=True,
                percent=coverage_percent,
                observation_count=obs_count,
            ),
            statistics=StatisticsMetrics(
                average_temperature=avg_temp,
                minimum_temperature=metrics.get("minimum_temperature"),
                maximum_temperature=metrics.get("maximum_temperature"),
                average_feels_like_temperature=metrics.get("average_feels_like_temperature"),
                average_humidity=metrics.get("average_humidity"),
                average_wind_speed=metrics.get("average_wind_speed"),
                total_precipitation=metrics.get("total_precipitation", 0.0),
            ),
            period=period_enum.value,
            average_temperature=avg_temp,
            minimum_temperature=metrics.get("minimum_temperature"),
            maximum_temperature=metrics.get("maximum_temperature"),
            coverage_percent=coverage_percent,
            observation_count=obs_count,
            available_from=earliest_str,
            available_to=latest_str,
        )
