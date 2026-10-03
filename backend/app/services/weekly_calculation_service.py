"""Weekly Calculation Service for Monthly Weather Report.

Architecture Rules:
- Backend performs all numerical calculations.
- Segments calendar months into weekly periods:
  - Week 1: 1st to 7th
  - Week 2: 8th to 14th
  - Week 3: 15th to 21st
  - Week 4: 22nd to 28th
  - Remaining Days: 29th to month end (if month has > 28 days).
- Never labels remaining days as "Week 5".
- Never silently discards remaining days.
- Calculates averages strictly from valid observations.
- Never replaces missing temperatures with 0.
- Flags incomplete periods clearly.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.monthly_report_schema import WeeklyPeriodReport
from app.services.average_temperature_calculator import AverageTemperatureCalculator
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.location_service import WELL_KNOWN_INDIAN_CITIES, normalize_name
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WeeklyCalculationResult:
    """Encapsulates the calculation output for a monthly weather report."""

    city_display: str
    city_name: str
    year: int
    month_number: int
    month_name: str
    month_display: str
    weekly_reports: List[WeeklyPeriodReport]
    is_available: bool
    highest_week: Optional[Dict[str, Any]]
    lowest_week: Optional[Dict[str, Any]]
    pattern_hint: Optional[str]
    total_valid_observations: int
    expected_month_days: int
    message: Optional[str] = None


class WeeklyCalculationService:
    """Service performing deterministic weekly segmentation and temperature averaging for a month."""

    def __init__(
        self,
        historical_service: Optional[HistoricalWeatherService] = None,
        calculator: Optional[AverageTemperatureCalculator] = None,
    ) -> None:
        self.historical_service = historical_service or HistoricalWeatherService()
        self.calculator = calculator or AverageTemperatureCalculator()

    @staticmethod
    def get_month_weekly_periods(year: int, month: int) -> List[Dict[str, Any]]:
        """Divide a calendar month into weekly periods plus remaining days.

        Rules:
        - Week 1: days 1-7
        - Week 2: days 8-14
        - Week 3: days 15-21
        - Week 4: days 22-28
        - Remaining Days: days 29-end of month (if total_days > 28)
        - Never call remaining days "Week 5".
        """
        num_days = calendar.monthrange(year, month)[1]
        month_abbr = calendar.month_abbr[month]

        periods = []
        standard_ranges = [(1, 7), (8, 14), (15, 21), (22, 28)]

        for week_idx, (start_day, end_day) in enumerate(standard_ranges, start=1):
            periods.append({
                "week": f"Week {week_idx}",
                "start_day": start_day,
                "end_day": end_day,
                "date_range": f"{month_abbr} {start_day} - {month_abbr} {end_day}",
                "start_date": f"{year:04d}-{month:02d}-{start_day:02d}",
                "end_date": f"{year:04d}-{month:02d}-{end_day:02d}",
                "expected_days": 7,
                "is_remaining": False,
            })

        if num_days > 28:
            start_day = 29
            end_day = num_days
            periods.append({
                "week": "Remaining Days",
                "start_day": start_day,
                "end_day": end_day,
                "date_range": f"{month_abbr} {start_day} - {month_abbr} {end_day}",
                "start_date": f"{year:04d}-{month:02d}-{start_day:02d}",
                "end_date": f"{year:04d}-{month:02d}-{end_day:02d}",
                "expected_days": end_day - start_day + 1,
                "is_remaining": True,
            })

        return periods

    @staticmethod
    def format_city_display(city: str, location_info: Optional[Dict[str, Any]] = None) -> str:
        """Format city for report header, matching 'City: Indore, Madhya Pradesh'."""
        if not location_info:
            norm = normalize_name(city)
            if norm in WELL_KNOWN_INDIAN_CITIES:
                known = WELL_KNOWN_INDIAN_CITIES[norm]
                admin1 = known.get("admin1")
                name = known.get("name", city)
                return f"{name}, {admin1}" if admin1 else name
            return city.strip().title()

        name = location_info.get("city") or location_info.get("name") or city
        admin1 = location_info.get("admin1")
        if admin1:
            return f"{name}, {admin1}"

        formatted = location_info.get("formatted_address")
        if formatted:
            # If formatted is "Indore, Madhya Pradesh, India", we can take "Indore, Madhya Pradesh"
            parts = [p.strip() for p in formatted.split(",")]
            if len(parts) >= 3 and parts[-1].lower() == "india":
                return f"{parts[0]}, {parts[1]}"
            return formatted

        return name

    def calculate_monthly_weekly_averages(
        self,
        city: str,
        year: int,
        month: int,
    ) -> WeeklyCalculationResult:
        """Fetch historical temperatures for a month and calculate deterministic weekly averages.

        Args:
            city: City name string.
            year: Calendar year (e.g. 2026).
            month: Month integer (1-12).

        Returns:
            WeeklyCalculationResult with structured weekly reports, extremes, and availability flag.
        """
        if not city or not city.strip():
            raise ValueError("City name cannot be empty.")

        clean_city = city.strip()
        num_days = calendar.monthrange(year, month)[1]
        start_date_str = f"{year:04d}-{month:02d}-01"
        end_date_str = f"{year:04d}-{month:02d}-{num_days:02d}"

        month_name = calendar.month_name[month]
        month_display = f"{month_name} {year}"

        logger.info(
            "Fetching historical temperatures for Monthly Report: city='%s', month='%s' (%s to %s)",
            clean_city,
            month_display,
            start_date_str,
            end_date_str,
        )

        hist_data = self.historical_service.fetch_historical_temperatures(
            city=clean_city,
            start_date=start_date_str,
            end_date=end_date_str,
        )

        resolved_city = hist_data.get("city", clean_city)
        location_meta = hist_data.get("location")
        city_display = self.format_city_display(resolved_city, location_meta)

        dates = hist_data.get("dates", [])
        raw_temps = hist_data.get("temperatures", [])
        temp_by_date: Dict[str, float] = {}

        for d_str, t_val in zip(dates, raw_temps):
            if t_val is not None:
                try:
                    temp_by_date[d_str] = float(t_val)
                except (ValueError, TypeError):
                    continue

        periods = self.get_month_weekly_periods(year, month)
        weekly_reports: List[WeeklyPeriodReport] = []
        total_valid_obs = 0
        periods_with_averages: List[Tuple[WeeklyPeriodReport, float]] = []

        for period_def in periods:
            w_name = period_def["week"]
            d_range = period_def["date_range"]
            s_date = period_def["start_date"]
            e_date = period_def["end_date"]
            expected_days = period_def["expected_days"]
            s_day = period_def["start_day"]
            e_day = period_def["end_day"]

            period_valid_temps: List[float] = []
            for d in range(s_day, e_day + 1):
                iso_key = f"{year:04d}-{month:02d}-{d:02d}"
                if iso_key in temp_by_date:
                    period_valid_temps.append(temp_by_date[iso_key])

            obs_count = len(period_valid_temps)
            total_valid_obs += obs_count

            if obs_count == 0:
                avg_temp = None
                is_comp = False
                note = "Data unavailable"
            else:
                avg_temp = self.calculator.calculate_average_temperature(period_valid_temps, decimals=1)
                is_comp = (obs_count == expected_days)
                note = None if is_comp else f"Incomplete data ({obs_count}/{expected_days} days)"

            report = WeeklyPeriodReport(
                week=w_name,
                date_range=d_range,
                start_date=s_date,
                end_date=e_date,
                average_temperature=avg_temp,
                observation_count=obs_count,
                expected_days=expected_days,
                is_complete=is_comp,
                note=note,
            )
            weekly_reports.append(report)

            if avg_temp is not None:
                periods_with_averages.append((report, avg_temp))

        # Check if entire month has 0 observations
        if total_valid_obs == 0 or not periods_with_averages:
            logger.warning(
                "Historical weather data is unavailable for city='%s', period='%s'",
                clean_city,
                month_display,
            )
            return WeeklyCalculationResult(
                city_display=city_display,
                city_name=resolved_city,
                year=year,
                month_number=month,
                month_name=month_name,
                month_display=month_display,
                weekly_reports=weekly_reports,
                is_available=False,
                highest_week=None,
                lowest_week=None,
                pattern_hint=None,
                total_valid_observations=0,
                expected_month_days=num_days,
                message="Historical weather data is currently unavailable for the selected period.",
            )

        # Pre-compute highest and lowest weekly averages
        highest_tuple = max(periods_with_averages, key=lambda item: item[1])
        lowest_tuple = min(periods_with_averages, key=lambda item: item[1])

        highest_week = {
            "week": highest_tuple[0].week,
            "date_range": highest_tuple[0].date_range,
            "average_temperature": highest_tuple[1],
        }
        lowest_week = {
            "week": lowest_tuple[0].week,
            "date_range": lowest_tuple[0].date_range,
            "average_temperature": lowest_tuple[1],
        }

        diff = round(highest_tuple[1] - lowest_tuple[1], 1)
        if diff <= 1.5:
            pattern_hint = (
                f"Relatively stable and consistent temperatures throughout the analyzed period with minimal variation under {max(diff, 0.5):.1f}°C."
            )
        elif diff <= 3.0:
            pattern_hint = (
                f"Moderate temperature consistency with a mild fluctuation range of {diff:.1f}°C between the warmest and coolest weeks."
            )
        else:
            pattern_hint = (
                f"Noticeable temperature variation across the month with a difference of {diff:.1f}°C between peak and low weekly averages."
            )

        return WeeklyCalculationResult(
            city_display=city_display,
            city_name=resolved_city,
            year=year,
            month_number=month,
            month_name=month_name,
            month_display=month_display,
            weekly_reports=weekly_reports,
            is_available=True,
            highest_week=highest_week,
            lowest_week=lowest_week,
            pattern_hint=pattern_hint,
            total_valid_observations=total_valid_obs,
            expected_month_days=num_days,
            message=None,
        )
