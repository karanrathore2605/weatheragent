"""Statistics service for deterministic Open-Meteo historical weather calculations."""

import calendar
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config.settings import settings
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import (
    CoverageInfo,
    DailyRecord,
    MonthlyAverage,
    StatisticsMetrics,
    StatisticsPeriod,
    WeatherStatisticsResponse,
    WeatherSummaryResponse,
)
from app.services.average_temperature_calculator import AverageTemperatureCalculator
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.llm_service import LLMService
from app.services.weather.open_meteo_client import OpenMeteoClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


def subtract_calendar_months(source_date: date, months: int) -> date:
    """Accurately subtract a given number of calendar months from a date.

    Proper calendar calculation handling leap years, variable days in months,
    and clamping to the last valid day of the resulting month.
    """
    new_year = source_date.year
    new_month = source_date.month - months
    while new_month <= 0:
        new_year -= 1
        new_month += 12
    max_days = calendar.monthrange(new_year, new_month)[1]
    new_day = min(source_date.day, max_days)
    return date(new_year, new_month, new_day)


def get_month_window(year: int, month: int) -> Dict[str, Any]:
    """Accurately compute calendar month bounds and metadata for a year and month."""
    num_days = calendar.monthrange(year, month)[1]
    return {
        "year": year,
        "month_num": month,
        "month_name": calendar.month_name[month],
        "start_date": date(year, month, 1),
        "end_date": date(year, month, num_days),
        "total_days": num_days,
    }


def get_candidate_months_backwards(reference_date: date, count: int) -> List[Dict[str, Any]]:
    """Generate calendar month windows starting from reference_date's month going backwards.

    Returns months in reverse chronological order: [current_month, prev_month, ...].
    """
    months: List[Dict[str, Any]] = []
    total_months = reference_date.year * 12 + (reference_date.month - 1)
    for offset in range(count):
        m_index = total_months - offset
        target_year = m_index // 12
        target_month = (m_index % 12) + 1
        months.append(get_month_window(target_year, target_month))
    return months


def get_calendar_months(reference_date: date, duration: int) -> List[Dict[str, Any]]:
    """Accurately compute the sequence of complete calendar months ending at reference_date's month.

    Example:
    If reference_date is in October 2026 and duration is 5:
    Returns 5 calendar month dictionaries:
    June 2026, July 2026, August 2026, September 2026, October 2026.

    Each item contains:
    - year: int
    - month_num: int (1-12)
    - month_name: str (e.g. 'June')
    - start_date: date (e.g. date(2026, 6, 1))
    - end_date: date (e.g. date(2026, 6, 30))
    - total_days: int (number of calendar days in month, e.g. 30, 31, 28/29)
    """
    ref_year = reference_date.year
    ref_month = reference_date.month

    months: List[Dict[str, Any]] = []
    for offset in range(duration - 1, -1, -1):
        total_months = ref_year * 12 + (ref_month - 1) - offset
        target_year = total_months // 12
        target_month = (total_months % 12) + 1
        num_days = calendar.monthrange(target_year, target_month)[1]
        m_start = date(target_year, target_month, 1)
        m_end = date(target_year, target_month, num_days)
        m_name = calendar.month_name[target_month]

        months.append({
            "year": target_year,
            "month_num": target_month,
            "month_name": m_name,
            "start_date": m_start,
            "end_date": m_end,
            "total_days": num_days,
        })
    return months


class StatisticsService:
    """Service computing historical temperature statistics via Open-Meteo Archive API."""

    def __init__(
        self,
        historical_service: Optional[HistoricalWeatherService] = None,
        repository: Optional[WeatherObservationRepository] = None,
        open_meteo_client: Optional[OpenMeteoClient] = None,
        min_coverage: Optional[float] = None,
        temperature_calculator: Optional[AverageTemperatureCalculator] = None,
        calculator: Optional[Any] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        if historical_service is not None:
            self.historical_service = historical_service
        else:
            self.historical_service = HistoricalWeatherService(
                open_meteo_client=open_meteo_client,
                repository=repository,
            )
        self.repository = repository
        self.min_coverage = (
            min_coverage if min_coverage is not None else settings.min_statistics_coverage
        )
        self.temperature_calculator = temperature_calculator or AverageTemperatureCalculator()
        self.llm_service = llm_service or LLMService()

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

        Week: 1, 2, 3
        Month: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        """
        try:
            val = int(period_value)
        except (ValueError, TypeError):
            raise ValueError("Period duration must be an integer.")

        if period == StatisticsPeriod.WEEK:
            if val not in (1, 2, 3):
                raise ValueError(
                    f"Invalid week duration: {val}. Supported durations for week: 1, 2, or 3 weeks."
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
        reference_date: Optional[Union[date, datetime]] = None,
    ) -> Tuple[date, date, int]:
        """Compute calendar date bounds for the specified period and duration.

        Week:
        - 1 Week  = previous 7 days
        - 2 Weeks = previous 14 days
        - 3 Weeks = previous 21 days

        Month:
        - 1 to 12 Months = previous 1 to 12 calendar months (proper calendar calculation)

        Returns:
            (start_date, end_date, expected_days)
        """
        if isinstance(period_value, datetime) or isinstance(period_value, date):
            reference_date = period_value
            period_value = 1

        period_enum = cls.parse_period(period)
        duration = cls.validate_period_value(period_enum, int(period_value))

        if reference_date is None:
            end_date = datetime.now(timezone.utc).date()
        elif isinstance(reference_date, datetime):
            end_date = reference_date.date()
        else:
            end_date = reference_date

        if period_enum == StatisticsPeriod.WEEK:
            days = duration * 7
            start_date = end_date - timedelta(days=days)
            expected_days = days

        elif period_enum == StatisticsPeriod.MONTH:
            month_windows = get_calendar_months(end_date, duration)
            start_date = month_windows[0]["start_date"]
            end_date = month_windows[-1]["end_date"]
            expected_days = sum(m["total_days"] for m in month_windows)

        else:
            raise ValueError(f"Unsupported period: {period_enum}")

        return start_date, end_date, expected_days

    def calculate_average_weather(
        self,
        city: str,
        period: Union[StatisticsPeriod, str] = StatisticsPeriod.WEEK,
        period_value: int = 1,
        duration: Optional[int] = None,
        reference_date: Optional[Union[date, datetime]] = None,
    ) -> WeatherStatisticsResponse:
        """Calculate deterministic average temperature for a city over a defined duration.

        Flow:
        1. Validate city, period, and duration.
        2. Compute date range (previous 7-28 days or 1-12 calendar months).
        3. Request historical data via HistoricalWeatherService (Open-Meteo Archive API).
        4. Validate temperature data, filter nulls without fabricating numbers.
        5. For multi-month requests, calculate individual monthly averages and overall average.
        6. For week requests, calculate single average temperature.
        7. Return structured WeatherStatisticsResponse.
        """
        valid_city = self.validate_city_input(city)
        period_enum = self.parse_period(period)
        effective_duration = duration if duration is not None else period_value
        valid_duration = self.validate_period_value(period_enum, effective_duration)

        if reference_date is None:
            ref_date = datetime.now(timezone.utc).date()
        elif isinstance(reference_date, datetime):
            ref_date = reference_date.date()
        else:
            ref_date = reference_date

        start_date, end_date, expected_days = self.get_date_range(
            period=period_enum,
            period_value=valid_duration,
            reference_date=ref_date,
        )

        period_label = (
            f"Previous {valid_duration} {period_enum.value.title() if valid_duration == 1 else period_enum.value.title() + 's'}"
        )

        if period_enum == StatisticsPeriod.MONTH:
            candidate_windows = get_candidate_months_backwards(ref_date, valid_duration + 1)
            fetch_start = candidate_windows[-1]["start_date"]
            fetch_end = candidate_windows[0]["end_date"]
        else:
            fetch_start = start_date
            fetch_end = end_date

        logger.info(
            "Computing %s historical statistics for '%s' (%s to %s) via Open-Meteo",
            period_label,
            valid_city,
            fetch_start.isoformat(),
            fetch_end.isoformat(),
        )

        # Retrieve observations from Open-Meteo via HistoricalWeatherService
        result = self.historical_service.fetch_historical_temperatures(
            city=valid_city,
            start_date=fetch_start.isoformat(),
            end_date=fetch_end.isoformat(),
        )

        resolved_city = result.get("city", valid_city)
        dates = result.get("dates", [])
        raw_temperatures = result.get("temperatures", [])

        # ===================================================================
        # Branch 1: WEEK CALCULATION (Daily breakdown + overall average)
        # ===================================================================
        if period_enum == StatisticsPeriod.WEEK:
            raw_valid_temps: List[float] = []
            daily_records: List[DailyRecord] = []

            temp_map: Dict[str, Any] = dict(zip(dates, raw_temperatures))

            curr_d = start_date
            while curr_d <= end_date:
                d_str = curr_d.isoformat()
                formatted_d = curr_d.strftime("%b %d")
                t = temp_map.get(d_str)

                if t is not None:
                    try:
                        raw_t = float(t)
                        raw_valid_temps.append(raw_t)
                        temp_rounded = round(raw_t, 1)

                        if ref_date and curr_d == ref_date and curr_d == datetime.now(timezone.utc).date():
                            now_utc = datetime.now(timezone.utc)
                            cov_pct = round(min(100.0, max(5.0, (now_utc.hour / 24.0) * 100.0)), 1)
                            status_str = f"{int(cov_pct)}%"
                        else:
                            cov_pct = 100.0
                            status_str = "100%"

                        daily_records.append(
                            DailyRecord(
                                date=d_str,
                                formatted_date=formatted_d,
                                average_temperature_celsius=temp_rounded,
                                coverage_percentage=cov_pct,
                                status=status_str,
                            )
                        )
                    except (ValueError, TypeError):
                        daily_records.append(
                            DailyRecord(
                                date=d_str,
                                formatted_date=formatted_d,
                                average_temperature_celsius=None,
                                coverage_percentage=0.0,
                                status="Missing",
                            )
                        )
                else:
                    daily_records.append(
                        DailyRecord(
                            date=d_str,
                            formatted_date=formatted_d,
                            average_temperature_celsius=None,
                            coverage_percentage=0.0,
                            status="Missing",
                        )
                    )
                curr_d += timedelta(days=1)

            observation_days = len(raw_valid_temps)
            coverage_percent = round(
                min(100.0, (observation_days / expected_days) * 100.0) if expected_days > 0 else 0.0,
                1,
            )

            # Insufficient data condition: 0 observations retrieved
            if observation_days == 0:
                logger.warning(
                    "Insufficient historical data for '%s' (%s): 0 observations retrieved",
                    resolved_city,
                    period_label,
                )
                return WeatherStatisticsResponse(
                    city=resolved_city,
                    provider="Open-Meteo",
                    period_type=period_enum.value,
                    duration=valid_duration,
                    period_value=valid_duration,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    monthly_averages=None,
                    daily_records=daily_records if daily_records else None,
                    daily_breakdown=daily_records if daily_records else None,
                    overall_average_temperature_celsius=None,
                    average_temperature_celsius=None,
                    total_observation_days=observation_days,
                    observation_days=observation_days,
                    data_coverage_percentage=coverage_percent,
                    coverage_percentage=coverage_percent,
                    data_coverage={"complete": False},
                    data_source="Open-Meteo",
                    coverage=CoverageInfo(
                        requested=f"{period_label} ({expected_days} days)",
                        available=f"{observation_days} days ({coverage_percent}%)",
                        complete=False,
                        percent=coverage_percent,
                        observation_count=observation_days,
                    ),
                    statistics=None,
                    status="INSUFFICIENT_HISTORICAL_DATA",
                    message="Unable to retrieve historical weather data right now. Please try again.",
                    period=period_enum.value,
                    average_temperature=None,
                    coverage_percent=coverage_percent,
                    observation_count=observation_days,
                )

            # Calculate pure average temperature strictly from valid daily mean observations
            avg_temp = self.temperature_calculator.calculate_average_temperature(raw_valid_temps, decimals=1)

            return WeatherStatisticsResponse(
                city=resolved_city,
                provider="Open-Meteo",
                period_type=period_enum.value,
                duration=valid_duration,
                period_value=valid_duration,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                monthly_averages=None,
                daily_records=daily_records,
                daily_breakdown=daily_records,
                overall_average_temperature_celsius=avg_temp,
                average_temperature_celsius=avg_temp,
                total_observation_days=observation_days,
                observation_days=observation_days,
                data_coverage_percentage=coverage_percent,
                coverage_percentage=coverage_percent,
                data_coverage={"complete": True},
                data_source="Open-Meteo",
                coverage=CoverageInfo(
                    requested=f"{period_label} ({expected_days} days)",
                    available=f"{observation_days} days ({coverage_percent}%)",
                    complete=True,
                    percent=coverage_percent,
                    observation_count=observation_days,
                ),
                statistics=StatisticsMetrics(
                    average_temperature=avg_temp,
                ),
                status="SUCCESS",
                message=None,
                period=period_enum.value,
                average_temperature=avg_temp,
                coverage_percent=coverage_percent,
                observation_count=observation_days,
            )

        # ===================================================================
        # Branch 2: MONTH CALCULATION (Month-by-month breakdown + overall average)
        # ===================================================================
        daily_temp_map: Dict[str, float] = {}
        for d_str, t in zip(dates, raw_temperatures):
            if t is not None:
                try:
                    daily_temp_map[d_str] = float(t)
                except (ValueError, TypeError):
                    continue

        candidate_windows = get_candidate_months_backwards(ref_date, valid_duration + 1)
        qualifying_windows: List[Dict[str, Any]] = []

        for m in candidate_windows:
            m_start = m["start_date"]
            m_end = m["end_date"]
            m_total_days = m["total_days"]

            month_valid_temps: List[float] = []
            curr_d = m_start
            while curr_d <= m_end:
                d_key = curr_d.isoformat()
                if d_key in daily_temp_map:
                    month_valid_temps.append(daily_temp_map[d_key])
                curr_d += timedelta(days=1)

            obs_count = len(month_valid_temps)
            cov_pct = round((obs_count / m_total_days) * 100.0, 1) if m_total_days > 0 else 0.0
            month_avg = self.temperature_calculator.calculate_average_temperature(month_valid_temps, decimals=1)

            is_current_month = (m["year"] == ref_date.year and m["month_num"] == ref_date.month)
            is_incomplete_current_month = is_current_month and (ref_date.day < m_total_days)

            if is_incomplete_current_month:
                current_month_min_cov = 90.0 if self.min_coverage > 0.0 else 0.0
                qualifies = (cov_pct >= current_month_min_cov)
                if not qualifies:
                    logger.info(
                        "Current month %s %s coverage %.1f%% < 90%%; skipping incomplete current month",
                        m["month_name"],
                        m["year"],
                        cov_pct,
                    )
            else:
                qualifies = (cov_pct >= self.min_coverage)

            if qualifies:
                m_item = dict(m)
                m_item["temps"] = month_valid_temps
                m_item["obs_count"] = obs_count
                m_item["cov_pct"] = cov_pct
                m_item["avg_temp"] = month_avg
                qualifying_windows.append(m_item)

                if len(qualifying_windows) == valid_duration:
                    break

        # If more qualifying months needed due to missing historical data
        offset = valid_duration + 1
        max_lookback = valid_duration + 24
        while len(qualifying_windows) < valid_duration and offset < max_lookback:
            total_months = ref_date.year * 12 + (ref_date.month - 1) - offset
            t_year = total_months // 12
            t_month = (total_months % 12) + 1
            m = get_month_window(t_year, t_month)

            m_start = m["start_date"]
            m_end = m["end_date"]
            extra_res = self.historical_service.fetch_historical_temperatures(
                city=valid_city,
                start_date=m_start.isoformat(),
                end_date=m_end.isoformat(),
            )
            for d_str, t in zip(extra_res.get("dates", []), extra_res.get("temperatures", [])):
                if t is not None:
                    try:
                        daily_temp_map[d_str] = float(t)
                    except (ValueError, TypeError):
                        continue

            month_valid_temps = []
            curr_d = m_start
            while curr_d <= m_end:
                d_key = curr_d.isoformat()
                if d_key in daily_temp_map:
                    month_valid_temps.append(daily_temp_map[d_key])
                curr_d += timedelta(days=1)

            obs_count = len(month_valid_temps)
            cov_pct = round((obs_count / m["total_days"]) * 100.0, 1) if m["total_days"] > 0 else 0.0
            month_avg = self.temperature_calculator.calculate_average_temperature(month_valid_temps, decimals=1)

            if cov_pct >= self.min_coverage:
                m_item = dict(m)
                m_item["temps"] = month_valid_temps
                m_item["obs_count"] = obs_count
                m_item["cov_pct"] = cov_pct
                m_item["avg_temp"] = month_avg
                qualifying_windows.append(m_item)

            offset += 1

        all_valid_temps: List[float] = []
        for q in qualifying_windows:
            all_valid_temps.extend(q["temps"])

        total_observation_days = len(all_valid_temps)
        expected_days = sum(q["total_days"] for q in qualifying_windows)
        overall_coverage = round(
            min(100.0, (total_observation_days / expected_days) * 100.0) if expected_days > 0 else 0.0,
            1,
        )

        if total_observation_days == 0 or not qualifying_windows:
            logger.warning(
                "Insufficient historical data for '%s' (%s): 0 observations retrieved",
                resolved_city,
                period_label,
            )
            return WeatherStatisticsResponse(
                city=resolved_city,
                provider="Open-Meteo",
                period_type=period_enum.value,
                duration=valid_duration,
                period_value=valid_duration,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                monthly_averages=[],
                overall_average_temperature_celsius=None,
                average_temperature_celsius=None,
                total_observation_days=0,
                observation_days=0,
                data_coverage_percentage=0.0,
                coverage_percentage=0.0,
                data_coverage={"complete": False},
                data_source="Open-Meteo",
                coverage=CoverageInfo(
                    requested=f"{period_label} ({expected_days} days)",
                    available=f"0 days (0.0%)",
                    complete=False,
                    percent=0.0,
                    observation_count=0,
                ),
                statistics=None,
                status="INSUFFICIENT_HISTORICAL_DATA",
                message="Unable to retrieve historical weather data right now. Please try again.",
                period=period_enum.value,
                average_temperature=None,
                coverage_percent=0.0,
                observation_count=0,
            )

        # Sort chronologically (earliest to latest)
        qualifying_windows.reverse()

        monthly_averages: List[MonthlyAverage] = [
            MonthlyAverage(
                month=q["month_name"],
                year=q["year"],
                average_temperature_celsius=q["avg_temp"],
                observation_days=q["obs_count"],
                total_days=q["total_days"],
                coverage_percentage=q["cov_pct"],
                start_date=q["start_date"].isoformat(),
                end_date=q["end_date"].isoformat(),
            )
            for q in qualifying_windows
        ]

        overall_avg = self.temperature_calculator.calculate_average_temperature(all_valid_temps, decimals=2)
        final_start_date = qualifying_windows[0]["start_date"].isoformat()
        final_end_date = qualifying_windows[-1]["end_date"].isoformat()

        return WeatherStatisticsResponse(
            city=resolved_city,
            provider="Open-Meteo",
            period_type=period_enum.value,
            duration=valid_duration,
            period_value=valid_duration,
            start_date=final_start_date,
            end_date=final_end_date,
            monthly_averages=monthly_averages,
            overall_average_temperature_celsius=overall_avg,
            average_temperature_celsius=overall_avg,
            total_observation_days=total_observation_days,
            observation_days=total_observation_days,
            data_coverage_percentage=overall_coverage,
            coverage_percentage=overall_coverage,
            data_coverage={"complete": True},
            data_source="Open-Meteo",
            coverage=CoverageInfo(
                requested=f"{period_label} ({expected_days} days)",
                available=f"{total_observation_days} days ({overall_coverage}%)",
                complete=True,
                percent=overall_coverage,
                observation_count=total_observation_days,
            ),
            statistics=StatisticsMetrics(
                average_temperature=overall_avg,
            ),
            status="SUCCESS",
            message=None,
            period=period_enum.value,
            average_temperature=overall_avg,
            coverage_percent=overall_coverage,
            observation_count=total_observation_days,
        )

    def get_weather_summary(
        self,
        city: str,
        period: Union[StatisticsPeriod, str] = StatisticsPeriod.WEEK,
        period_value: int = 1,
        duration: Optional[int] = None,
        reference_date: Optional[Union[date, datetime]] = None,
    ) -> WeatherSummaryResponse:
        """Compute deterministic statistics and generate an AI natural-language narrative.

        Fault-Tolerant Behavior:
        - Calculates deterministic statistics first.
        - If statistics return INSUFFICIENT_HISTORICAL_DATA, returns directly without calling LLM.
        - If statistics succeed, delegates to LLMService.generate_weather_summary.
        - If LLM generation succeeds, returns status='SUCCESS' with summary text.
        - If LLM generation fails (e.g. unconfigured API key, timeout, rate limit), returns status='PARTIAL_SUCCESS'
          with complete deterministic statistics intact and an informative guidance message.
        """
        stats_response = self.calculate_average_weather(
            city=city,
            period=period,
            period_value=period_value,
            duration=duration,
            reference_date=reference_date,
        )

        effective_duration = duration if duration is not None else period_value
        period_str = stats_response.period_type

        # If data is insufficient, do not call LLM
        if stats_response.status == "INSUFFICIENT_HISTORICAL_DATA":
            return WeatherSummaryResponse(
                status="INSUFFICIENT_HISTORICAL_DATA",
                city=stats_response.city,
                period_type=period_str,
                duration=effective_duration,
                statistics=stats_response,
                summary=None,
                message=stats_response.message or "Unable to retrieve historical weather data right now. Please try again.",
            )

        # Attempt AI narrative generation via Groq LLM
        summary_text = self.llm_service.generate_weather_summary(
            city=stats_response.city,
            period=period_str,
            duration=effective_duration,
            statistics=stats_response.model_dump(),
            raise_on_error=False,
        )

        if summary_text:
            stats_response.summary = summary_text
            return WeatherSummaryResponse(
                status="SUCCESS",
                city=stats_response.city,
                period_type=period_str,
                duration=effective_duration,
                statistics=stats_response,
                summary=summary_text,
                message=None,
            )
        else:
            return WeatherSummaryResponse(
                status="PARTIAL_SUCCESS",
                city=stats_response.city,
                period_type=period_str,
                duration=effective_duration,
                statistics=stats_response,
                summary=None,
                message="Weather statistics are available, but the AI summary could not be generated right now.",
            )


