"""Monthly Weather Report Generation Service.

Suggested Architecture:
Historical Weather API
        ↓
Historical Weather Service
        ↓
Weekly Calculation Service
        ↓
Report Data
        ↓
Groq Summary Service
        ↓
Weather Report
"""

import calendar
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from app.schemas.monthly_report_schema import (
    MonthlyWeatherReportResponse,
    WeeklyPeriodReport,
)
from app.services.llm_service import LLMService
from app.services.weekly_calculation_service import WeeklyCalculationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def parse_month_and_year(
    month_input: Optional[Union[str, int]] = None,
    year_input: Optional[int] = None,
) -> Tuple[int, int]:
    """Parse various user month/year input formats into (year: int, month: int).

    Supported formats:
    - "August 2026" -> (2026, 8)
    - "Aug 2026" -> (2026, 8)
    - "2026-08" -> (2026, 8)
    - "August", year=2026 -> (2026, 8)
    - "8", year=2026 -> (2026, 8)
    - month_input=8, year_input=2026 -> (2026, 8)
    - Default if empty: current year and previous month (or current month)

    Raises:
        ValueError: If input format is invalid or out of bounds.
    """
    now = datetime.now(timezone.utc)
    current_year = now.year

    if not month_input and not year_input:
        # Default to previous month if available, else current
        if now.month == 1:
            return current_year - 1, 12
        return current_year, now.month - 1

    if isinstance(month_input, int):
        m = month_input
        y = int(year_input) if year_input else current_year
        if not (1 <= m <= 12):
            raise ValueError(f"Invalid month number: {m}. Must be between 1 and 12.")
        return y, m

    raw = str(month_input or "").strip()

    # Case 1: "YYYY-MM" or "YYYY/MM"
    match_iso = re.match(r"^(\d{4})[-/](\d{1,2})$", raw)
    if match_iso:
        y = int(match_iso.group(1))
        m = int(match_iso.group(2))
        if not (1 <= m <= 12):
            raise ValueError(f"Invalid month number: {m}. Must be between 1 and 12.")
        return y, m

    # Case 2: "Month YYYY" (e.g. "August 2026", "Aug 2026", "August, 2026")
    match_text_year = re.match(r"^([a-zA-Z]+)[,\s]+(\d{4})$", raw)
    if match_text_year:
        m_name = match_text_year.group(1).lower()
        y = int(match_text_year.group(2))
        for idx in range(1, 13):
            if calendar.month_name[idx].lower() == m_name or calendar.month_abbr[idx].lower() == m_name:
                return y, idx
        raise ValueError(f"Unknown month name '{match_text_year.group(1)}'.")

    # Case 3: Month name only (e.g. "August" with optional year_input)
    if raw.isalpha():
        m_lower = raw.lower()
        y = int(year_input) if year_input else current_year
        for idx in range(1, 13):
            if calendar.month_name[idx].lower() == m_lower or calendar.month_abbr[idx].lower() == m_lower:
                return y, idx
        raise ValueError(f"Unknown month name '{raw}'.")

    # Case 4: Numeric month string (e.g. "8" or "08")
    if raw.isdigit():
        m = int(raw)
        if not (1 <= m <= 12):
            raise ValueError(f"Invalid month number: {m}. Must be between 1 and 12.")
        y = int(year_input) if year_input else current_year
        return y, m

    # Case 5: If year_input is given and month_input was empty
    if year_input and not raw:
        return int(year_input), 1

    raise ValueError(f"Unrecognized month format: '{raw}'. Expected format like 'August 2026' or '2026-08'.")


class MonthlyReportService:
    """Production service coordinating Monthly Weather Report generation.

    Separates calculation logic from LLM logic and prepares data structured for future email reuse.
    """

    def __init__(
        self,
        calculation_service: Optional[WeeklyCalculationService] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        self.calculation_service = calculation_service or WeeklyCalculationService()
        self.llm_service = llm_service or LLMService()

    def generate_report(
        self,
        city: str,
        month_input: Optional[Union[str, int]] = None,
        year_input: Optional[int] = None,
    ) -> MonthlyWeatherReportResponse:
        """Generate a complete Monthly Weather Report.

        Flow:
        1. Parse and validate city and month/year.
        2. Calculate weekly averages deterministically via WeeklyCalculationService.
        3. If historical data is unavailable, return structured unavailable report.
        4. If calculated data is valid, send to Groq via LLMService for professional summary.
        5. Assemble structured MonthlyWeatherReportResponse with future email service payload.
        """
        year, month = parse_month_and_year(month_input, year_input)

        # Step 1: Calculate deterministic weekly averages
        calc_result = self.calculation_service.calculate_monthly_weekly_averages(
            city=city,
            year=year,
            month=month,
        )

        # Step 2: Handle data unavailability
        if not calc_result.is_available:
            return MonthlyWeatherReportResponse(
                city=calc_result.city_display,
                month=calc_result.month_display,
                year=calc_result.year,
                month_number=calc_result.month_number,
                weekly_averages=calc_result.weekly_reports,
                summary=None,
                status="UNAVAILABLE",
                message=calc_result.message or "Historical weather data is currently unavailable for the selected period.",
                highest_week=None,
                lowest_week=None,
                email_payload=None,
            )

        # Step 3: Format weekly data for LLM and future email service
        weekly_dicts = [w.model_dump() for w in calc_result.weekly_reports]

        # Step 4: Request Groq professional summary based strictly on calculated results
        summary_text = self.llm_service.generate_monthly_report_summary(
            city=calc_result.city_display,
            month=calc_result.month_display,
            weekly_averages=weekly_dicts,
            highest_week=calc_result.highest_week,
            lowest_week=calc_result.lowest_week,
            pattern_hint=calc_result.pattern_hint,
            raise_on_error=False,
        )

        status_code = "SUCCESS" if summary_text else "PARTIAL_SUCCESS"

        # Step 5: Build structured payload ready for future email service
        email_payload = {
            "city": calc_result.city_display,
            "month": calc_result.month_display,
            "year": calc_result.year,
            "month_number": calc_result.month_number,
            "weekly_table": [
                {
                    "week": w.week,
                    "date_range": w.date_range,
                    "average_temperature_celsius": w.average_temperature,
                    "formatted_temperature": f"{w.average_temperature:.1f}°C" if w.average_temperature is not None else "N/A",
                    "observation_count": w.observation_count,
                    "expected_days": w.expected_days,
                    "is_complete": w.is_complete,
                }
                for w in calc_result.weekly_reports
            ],
            "highest_week": calc_result.highest_week,
            "lowest_week": calc_result.lowest_week,
            "summary": summary_text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return MonthlyWeatherReportResponse(
            city=calc_result.city_display,
            month=calc_result.month_display,
            year=calc_result.year,
            month_number=calc_result.month_number,
            weekly_averages=calc_result.weekly_reports,
            summary=summary_text,
            status=status_code,
            message=None if summary_text else "Weather report generated; AI summary temporarily unavailable.",
            highest_week=calc_result.highest_week,
            lowest_week=calc_result.lowest_week,
            email_payload=email_payload,
        )
