"""Statistics service for deterministic meteorological calculations and data sufficiency checks."""

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

from app.config.settings import settings
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import StatisticsPeriod, WeatherStatisticsResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StatisticsService:
    """Production service for computing historical weather statistics from persistent observations.
    
    Architecture Rules:
    - Calculations are strictly deterministic (sum, min, max, average).
    - No LLM invocation for numerical computations.
    - Evaluates data coverage before returning statistics.
    - Returns structured insufficient_data responses when coverage is below threshold.
    - Date calculations are timezone-aware in UTC.
    """

    def __init__(
        self,
        repository: WeatherObservationRepository,
        min_coverage: Optional[float] = None,
    ) -> None:
        self.repository = repository
        self.min_coverage = (
            min_coverage if min_coverage is not None else settings.min_statistics_coverage
        )

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
        
        Raises:
            ValueError: If period is unsupported.
        """
        if isinstance(period, StatisticsPeriod):
            return period
        if not period or not isinstance(period, str):
            raise ValueError("Statistics period is required.")

        normalized = period.strip().lower()
        try:
            return StatisticsPeriod(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid statistics period '{period}'. Supported periods: week, month, year."
            )

    @staticmethod
    def get_date_range(
        period: StatisticsPeriod,
        reference_date: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime, int]:
        """Compute UTC start and end bounds for the specified calendar period.
        
        Calendar Period Definitions:
        - week: Monday 00:00:00 UTC to Sunday 23:59:59.999999 UTC of reference week.
        - month: 1st day of month 00:00:00 UTC to last day 23:59:59.999999 UTC.
        - year: Jan 1 00:00:00 UTC to Dec 31 23:59:59.999999 UTC.

        Returns:
            (start_date_utc, end_date_utc, expected_hourly_observations)
        """
        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        else:
            ref = ref.astimezone(timezone.utc)

        if period == StatisticsPeriod.WEEK:
            # ISO calendar week: Monday is weekday 0, Sunday is weekday 6
            start_date = (ref - timedelta(days=ref.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            expected_observations = 7 * 24  # 168 hours

        elif period == StatisticsPeriod.MONTH:
            start_date = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            days_in_month = calendar.monthrange(ref.year, ref.month)[1]
            end_date = ref.replace(
                day=days_in_month, hour=23, minute=59, second=59, microsecond=999999
            )
            expected_observations = days_in_month * 24

        elif period == StatisticsPeriod.YEAR:
            start_date = ref.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            is_leap = calendar.isleap(ref.year)
            days_in_year = 366 if is_leap else 365
            end_date = ref.replace(
                month=12, day=31, hour=23, minute=59, second=59, microsecond=999999
            )
            expected_observations = days_in_year * 24

        else:
            raise ValueError(f"Unsupported period: {period}")

        return start_date, end_date, expected_observations

    def calculate_average_weather(
        self,
        city: str,
        period: Union[StatisticsPeriod, str],
        reference_date: Optional[datetime] = None,
    ) -> WeatherStatisticsResponse:
        """Calculate deterministic weather statistics for a city over a defined period.
        
        Flow:
        1. Validate city and period.
        2. Compute timezone-aware date range.
        3. Query persistent observations from repository.
        4. Validate data coverage against minimum threshold.
        5. Compute averages, min, max, totals ignoring missing values.
        6. Return canonical WeatherStatisticsResponse.
        """
        valid_city = self.validate_city_input(city)
        period_enum = self.parse_period(period)
        start_date, end_date, expected_obs = self.get_date_range(period_enum, reference_date)

        logger.info(
            "Computing %s weather statistics for city='%s' between %s and %s",
            period_enum.value,
            valid_city,
            start_date.isoformat(),
            end_date.isoformat(),
        )

        observations = self.repository.get_observations_by_date_range(
            city=valid_city,
            start_date=start_date,
            end_date=end_date,
        )

        obs_count = len(observations)
        coverage_percent = round(
            min(100.0, (obs_count / expected_obs) * 100.0) if expected_obs > 0 else 0.0,
            1,
        )

        # Data sufficiency verification
        if coverage_percent < self.min_coverage:
            logger.info(
                "Insufficient data for '%s' (%s): coverage=%.1f%% < threshold=%.1f%% (count=%d/%d)",
                valid_city,
                period_enum.value,
                coverage_percent,
                self.min_coverage,
                obs_count,
                expected_obs,
            )
            earliest, latest = self.repository.check_available_data_range(valid_city)
            return WeatherStatisticsResponse(
                status="insufficient_data",
                city=valid_city,
                period=period_enum.value,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                observation_count=obs_count,
                coverage_percent=coverage_percent,
                available_from=earliest.strftime("%Y-%m-%d") if earliest else None,
                available_to=latest.strftime("%Y-%m-%d") if latest else None,
                message="Not enough historical weather data is available for the requested period.",
            )

        # Deterministic calculations ignoring nulls
        temperatures = [obs.temperature for obs in observations if obs.temperature is not None]
        avg_temp = round(sum(temperatures) / len(temperatures), 1) if temperatures else None
        min_temp = round(min(temperatures), 1) if temperatures else None
        max_temp = round(max(temperatures), 1) if temperatures else None

        feels_like = [
            obs.feels_like_temperature
            for obs in observations
            if obs.feels_like_temperature is not None
        ]
        avg_feels_like = round(sum(feels_like) / len(feels_like), 1) if feels_like else None

        humidities = [obs.humidity for obs in observations if obs.humidity is not None]
        avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else None

        wind_speeds = [obs.wind_speed for obs in observations if obs.wind_speed is not None]
        avg_wind_speed = round(sum(wind_speeds) / len(wind_speeds), 1) if wind_speeds else None

        precipitations = [obs.precipitation for obs in observations if obs.precipitation is not None]
        total_precip = round(sum(precipitations), 1) if precipitations else 0.0

        return WeatherStatisticsResponse(
            status="success",
            city=valid_city,
            period=period_enum.value,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            average_temperature=avg_temp,
            minimum_temperature=min_temp,
            maximum_temperature=max_temp,
            average_feels_like_temperature=avg_feels_like,
            average_humidity=avg_humidity,
            average_wind_speed=avg_wind_speed,
            total_precipitation=total_precip,
            observation_count=obs_count,
            coverage_percent=coverage_percent,
            message=None,
        )
