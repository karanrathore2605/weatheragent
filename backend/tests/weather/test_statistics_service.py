"""Unit tests for StatisticsService and Open-Meteo historical weather integration.

Covers the 12 required test scenarios:
1. 1 month
2. 2 months
3. 5 months (matching prompt example: 27.8, 28.4, 27.9, 29.1, 28.6 -> 28.36°C)
4. 12 months
5. Monthly grouping (proper calendar boundary assignment)
6. Monthly average calculation (deterministic 1-decimal rounding)
7. Overall average calculation (from daily observations, NOT average of rounded monthly averages)
8. Missing daily observations (partial coverage calculation)
9. Different month lengths (31, 30, 28 days)
10. Leap year February (29 days in 2024)
11. Week calculation remains unchanged (1-4 weeks, no monthly breakdown)
12. Correct API response mapping
"""

import calendar
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.schemas.weather_schema import StatisticsPeriod
from app.services.average_temperature_calculator import AverageTemperatureCalculator
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.statistics_service import (
    StatisticsService,
    get_calendar_months,
    subtract_calendar_months,
)


@pytest.fixture
def mock_historical_service() -> MagicMock:
    return MagicMock(spec=HistoricalWeatherService)


@pytest.fixture
def service(mock_historical_service: MagicMock) -> StatisticsService:
    return StatisticsService(
        historical_service=mock_historical_service,
        min_coverage=70.0,
    )


# ---------------------------------------------------------------------------
# Test 1: 1 Month
# ---------------------------------------------------------------------------
def test_indore_1_month(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test 1 month duration: October 2026 (31 days)."""
    ref_date = date(2026, 10, 15)
    start_date, end_date, expected_days = service.get_date_range("month", 1, ref_date)

    assert start_date == date(2026, 10, 1)
    assert end_date == date(2026, 10, 31)
    assert expected_days == 31

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(start_date + timedelta(days=i)) for i in range(31)],
        "temperatures": [28.0 for _ in range(31)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.period_type == "month"
    assert res.duration == 1
    assert res.total_observation_days == 31
    assert res.data_coverage_percentage == 100.0
    assert res.overall_average_temperature_celsius == 28.0
    assert res.average_temperature_celsius == 28.0
    assert res.monthly_averages is not None
    assert len(res.monthly_averages) == 1
    assert res.monthly_averages[0].month == "October"
    assert res.monthly_averages[0].year == 2026
    assert res.monthly_averages[0].average_temperature_celsius == 28.0
    assert res.monthly_averages[0].observation_days == 31
    assert res.monthly_averages[0].total_days == 31


# ---------------------------------------------------------------------------
# Test 2: 2 Months
# ---------------------------------------------------------------------------
def test_indore_2_months(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test 2 months duration: September (30) and October (31) = 61 days."""
    ref_date = date(2026, 10, 5)
    start_date, end_date, expected_days = service.get_date_range("month", 2, ref_date)

    assert start_date == date(2026, 9, 1)
    assert end_date == date(2026, 10, 31)
    assert expected_days == 61

    # September: 30 days @ 26.0°C; October: 31 days @ 28.0°C
    dates = [str(start_date + timedelta(days=i)) for i in range(expected_days)]
    temps = [26.0 if i < 30 else 28.0 for i in range(expected_days)]

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Indore", "month", duration=2, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.duration == 2
    assert len(res.monthly_averages) == 2

    # Check September
    assert res.monthly_averages[0].month == "September"
    assert res.monthly_averages[0].observation_days == 30
    assert res.monthly_averages[0].average_temperature_celsius == 26.0

    # Check October
    assert res.monthly_averages[1].month == "October"
    assert res.monthly_averages[1].observation_days == 31
    assert res.monthly_averages[1].average_temperature_celsius == 28.0

    # Overall: (30 * 26.0 + 31 * 28.0) / 61 = (780 + 868) / 61 = 1648 / 61 = 27.01639... -> 27.02
    assert res.overall_average_temperature_celsius == 27.02
    assert res.total_observation_days == 61


# ---------------------------------------------------------------------------
# Test 3: 5 Months (Matching User Example: 28.36°C)
# ---------------------------------------------------------------------------
def test_5_months_exact_prompt_example(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test 5 months: June (30d@27.8), July (31d@28.4), Aug (31d@27.9), Sep (30d@29.1), Oct (31d@28.6).
    Total days = 153.
    Sum = 30*27.8 + 31*28.4 + 31*27.9 + 30*29.1 + 31*28.6 = 834 + 880.4 + 864.9 + 873 + 886.6 = 4338.9
    Overall average = 4338.9 / 153 = 28.3588235... -> 28.36°C.
    """
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("month", 5, ref_date)

    assert start_date == date(2026, 6, 1)
    assert end_date == date(2026, 10, 31)
    assert expected_days == 153

    dates: list[str] = []
    temps: list[float] = []

    # June: 30 days @ 27.8
    for d in range(1, 31):
        dates.append(f"2026-06-{d:02d}")
        temps.append(27.8)

    # July: 31 days @ 28.4
    for d in range(1, 32):
        dates.append(f"2026-07-{d:02d}")
        temps.append(28.4)

    # August: 31 days @ 27.9
    for d in range(1, 32):
        dates.append(f"2026-08-{d:02d}")
        temps.append(27.9)

    # September: 30 days @ 29.1
    for d in range(1, 31):
        dates.append(f"2026-09-{d:02d}")
        temps.append(29.1)

    # October: 31 days @ 28.6
    for d in range(1, 32):
        dates.append(f"2026-10-{d:02d}")
        temps.append(28.6)

    assert len(dates) == 153
    assert len(temps) == 153

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Mumbai",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Mumbai", "month", duration=5, reference_date=ref_date)

    assert res.status == "SUCCESS"
    assert res.city == "Mumbai"
    assert res.period_type == "month"
    assert res.duration == 5
    assert res.start_date == "2026-06-01"
    assert res.end_date == "2026-10-31"
    assert res.total_observation_days == 153
    assert res.data_coverage_percentage == 100.0

    # Monthly breakdown checks
    assert len(res.monthly_averages) == 5
    expected_monthly = [
        ("June", 2026, 27.8, 30),
        ("July", 2026, 28.4, 31),
        ("August", 2026, 27.9, 31),
        ("September", 2026, 29.1, 30),
        ("October", 2026, 28.6, 31),
    ]
    for idx, (m_name, yr, exp_avg, exp_obs) in enumerate(expected_monthly):
        m_item = res.monthly_averages[idx]
        assert m_item.month == m_name
        assert m_item.year == yr
        assert m_item.average_temperature_celsius == exp_avg
        assert m_item.observation_days == exp_obs

    # Mathematically accurate overall average (decimals=2)
    assert res.overall_average_temperature_celsius == 28.36


# ---------------------------------------------------------------------------
# Test 4: 12 Months
# ---------------------------------------------------------------------------
def test_indore_12_months(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test 12 months duration: November 2025 to October 2026 (365 days)."""
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("month", 12, ref_date)

    assert start_date == date(2025, 11, 1)
    assert end_date == date(2026, 10, 31)
    assert expected_days == 365

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(start_date + timedelta(days=i)) for i in range(expected_days)],
        "temperatures": [25.0 for _ in range(expected_days)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=12, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.duration == 12
    assert len(res.monthly_averages) == 12
    assert res.monthly_averages[0].month == "November"
    assert res.monthly_averages[0].year == 2025
    assert res.monthly_averages[-1].month == "October"
    assert res.monthly_averages[-1].year == 2026
    assert res.overall_average_temperature_celsius == 25.0


# ---------------------------------------------------------------------------
# Test 5: Monthly Grouping
# ---------------------------------------------------------------------------
def test_monthly_grouping_boundaries(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test observations strictly fall into calendar months by date, ignoring order."""
    ref_date = date(2026, 8, 15)  # July and August 2026 (62 days total)

    # Supply mixed dates
    dates = ["2026-07-31", "2026-08-01", "2026-07-01", "2026-08-31"]
    temps = [25.0, 35.0, 27.0, 37.0]

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": dates,
        "temperatures": temps,
    }

    service.min_coverage = 0.0  # Allow low coverage to inspect grouping
    res = service.calculate_average_weather("Indore", "month", duration=2, reference_date=ref_date)

    assert len(res.monthly_averages) == 2
    july = res.monthly_averages[0]
    august = res.monthly_averages[1]

    assert july.month == "July"
    assert july.observation_days == 2  # 2026-07-01 (27) and 2026-07-31 (25)
    assert july.average_temperature_celsius == 26.0

    assert august.month == "August"
    assert august.observation_days == 2  # 2026-08-01 (35) and 2026-08-31 (37)
    assert august.average_temperature_celsius == 36.0


# ---------------------------------------------------------------------------
# Test 6: Monthly Average Calculation
# ---------------------------------------------------------------------------
def test_monthly_average_calculation() -> None:
    """Test deterministic monthly average rounded to 1 decimal place."""
    calc = AverageTemperatureCalculator()
    temps = [27.8, 27.9, 28.0, 28.1, 28.2]
    # Sum = 140.0 / 5 = 28.0
    assert calc.calculate_average_temperature(temps, decimals=1) == 28.0

    temps2 = [27.81, 28.45]
    # Sum = 56.26 / 2 = 28.13 -> 28.1
    assert calc.calculate_average_temperature(temps2, decimals=1) == 28.1


# ---------------------------------------------------------------------------
# Test 7: Overall Average NOT Simple Average of Monthly Averages
# ---------------------------------------------------------------------------
def test_overall_average_calculated_from_daily_observations(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Verify that overall average is mathematically computed from raw daily observations,
    NOT the unweighted average of rounded monthly numbers.
    
    Example:
    Month 1: 10 observations with sum 100 -> avg = 10.0
    Month 2: 20 observations with sum 400 -> avg = 20.0
    Unweighted monthly average = (10.0 + 20.0) / 2 = 15.0
    True daily average = (100 + 400) / 30 = 500 / 30 = 16.6666... -> 16.67
    """
    ref_date = date(2026, 8, 15)  # July and August 2026

    dates: list[str] = []
    temps: list[float] = []

    # July: 10 observations of 10.0
    for d in range(1, 11):
        dates.append(f"2026-07-{d:02d}")
        temps.append(10.0)

    # August: 20 observations of 20.0
    for d in range(1, 21):
        dates.append(f"2026-08-{d:02d}")
        temps.append(20.0)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": dates,
        "temperatures": temps,
    }

    service.min_coverage = 0.0
    res = service.calculate_average_weather("Indore", "month", duration=2, reference_date=ref_date)

    assert res.monthly_averages[0].average_temperature_celsius == 10.0
    assert res.monthly_averages[1].average_temperature_celsius == 20.0
    # Must be 16.67, NOT 15.0
    assert res.overall_average_temperature_celsius == 16.67
    assert res.total_observation_days == 30


# ---------------------------------------------------------------------------
# Test 8: Missing Daily Observations
# ---------------------------------------------------------------------------
def test_missing_daily_observations(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Test partial month coverage with missing days and None values."""
    ref_date = date(2026, 7, 31)  # July 2026 (31 days)

    # 25 valid days out of 31 days (Coverage = 25/31 = 80.6%)
    dates: list[str] = []
    temps: list[float] = []
    for d in range(1, 26):
        dates.append(f"2026-07-{d:02d}")
        temps.append(28.0)
    # 6 None values
    for d in range(26, 32):
        dates.append(f"2026-07-{d:02d}")
        temps.append(None)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Indore", "month", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.monthly_averages[0].observation_days == 25
    assert res.monthly_averages[0].total_days == 31
    assert res.monthly_averages[0].coverage_percentage == 80.6
    assert res.monthly_averages[0].average_temperature_celsius == 28.0
    assert res.overall_average_temperature_celsius == 28.0


# ---------------------------------------------------------------------------
# Test 9: Different Month Lengths
# ---------------------------------------------------------------------------
def test_different_month_lengths() -> None:
    """Test calendar month windows accurately identify month lengths (31, 30, 28)."""
    ref_date = date(2023, 4, 15)  # Jan (31), Feb (28 non-leap), Mar (31), Apr (30)
    months = get_calendar_months(ref_date, duration=4)

    assert len(months) == 4
    assert months[0]["month_name"] == "January" and months[0]["total_days"] == 31
    assert months[1]["month_name"] == "February" and months[1]["total_days"] == 28
    assert months[2]["month_name"] == "March" and months[2]["total_days"] == 31
    assert months[3]["month_name"] == "April" and months[3]["total_days"] == 30


# ---------------------------------------------------------------------------
# Test 10: Leap Year February
# ---------------------------------------------------------------------------
def test_leap_year_february() -> None:
    """Test February in leap year 2024 has 29 days."""
    ref_date = date(2024, 2, 10)
    months = get_calendar_months(ref_date, duration=1)

    assert len(months) == 1
    assert months[0]["month_name"] == "February"
    assert months[0]["year"] == 2024
    assert months[0]["total_days"] == 29
    assert months[0]["start_date"] == date(2024, 2, 1)
    assert months[0]["end_date"] == date(2024, 2, 29)


# ---------------------------------------------------------------------------
# Test 11: Week Calculation Remains Unchanged
# ---------------------------------------------------------------------------
def test_week_calculation_remains_unchanged(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Test that week calculations (1-4 weeks) do not return monthly breakdown."""
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("week", 1, ref_date)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(start_date + timedelta(days=i)) for i in range(7)],
        "temperatures": [28.0, 29.0, 30.0, 31.0, 29.5, 30.5, 31.0],
    }

    res = service.calculate_average_weather("Indore", "week", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.period_type == "week"
    assert res.duration == 1
    assert res.observation_days == 7
    assert res.coverage_percentage == 100.0
    assert res.average_temperature_celsius == 29.9
    # Week MUST NOT have monthly averages breakdown, but MUST have daily breakdown
    assert res.monthly_averages is None
    assert res.daily_records is not None
    assert len(res.daily_records) > 0


# ---------------------------------------------------------------------------
# Test 12: Correct API Response Mapping
# ---------------------------------------------------------------------------
def test_correct_api_response_mapping(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Verify all top-level keys in response match required schema."""
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("month", 2, ref_date)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Mumbai",
        "dates": [str(start_date + timedelta(days=i)) for i in range(expected_days)],
        "temperatures": [30.0 for _ in range(expected_days)],
    }

    res = service.calculate_average_weather("Mumbai", "month", duration=2, reference_date=ref_date)

    payload = res.model_dump()
    assert payload["city"] == "Mumbai"
    assert payload["period_type"] == "month"
    assert payload["duration"] == 2
    assert payload["start_date"] == start_date.isoformat()
    assert payload["end_date"] == end_date.isoformat()
    assert payload["provider"] in ("Open-Meteo", "open-meteo")
    assert "monthly_averages" in payload
    assert len(payload["monthly_averages"]) == 2
    assert payload["overall_average_temperature_celsius"] == 30.0
    assert payload["total_observation_days"] == expected_days
    assert payload["data_coverage_percentage"] == 100.0


# ---------------------------------------------------------------------------
# Test 13: Current Month Skipped When Under 90% Coverage (User Prompt Example)
# ---------------------------------------------------------------------------
def test_current_month_skipped_when_under_90_percent(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Current date: 2026-10-03, User selects: 4 Months.
    October coverage: 9.7% (3 observations / 31 days).
    Because 9.7% < 90%: SKIP October.
    Select: June, July, August, September (exactly 4 complete months).
    Final calculation: June + July + August + September.
    """
    ref_date = date(2026, 10, 3)

    # Provide data for June (30d), July (31d), August (31d), September (30d), and 3 days of October
    dates: list[str] = []
    temps: list[float] = []

    # June: 30 days @ 29.1
    for d in range(1, 31):
        dates.append(f"2026-06-{d:02d}")
        temps.append(29.1)
    # July: 31 days @ 26.7
    for d in range(1, 32):
        dates.append(f"2026-07-{d:02d}")
        temps.append(26.7)
    # August: 31 days @ 25.2
    for d in range(1, 32):
        dates.append(f"2026-08-{d:02d}")
        temps.append(25.2)
    # September: 30 days @ 25.3
    for d in range(1, 31):
        dates.append(f"2026-09-{d:02d}")
        temps.append(25.3)
    # October: 3 days @ 26.8 (9.7% coverage)
    for d in range(1, 4):
        dates.append(f"2026-10-{d:02d}")
        temps.append(26.8)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Bhopal", "month", duration=4, reference_date=ref_date)

    assert res.status == "SUCCESS"
    assert res.city == "Bhopal"
    assert res.duration == 4

    # Must contain exactly 4 qualifying months
    assert len(res.monthly_averages) == 4

    # Must be June, July, August, September (October must NOT be included)
    month_names = [m.month for m in res.monthly_averages]
    assert month_names == ["June", "July", "August", "September"]
    assert "October" not in month_names

    # Check each month
    assert res.monthly_averages[0].month == "June"
    assert res.monthly_averages[0].average_temperature_celsius == 29.1
    assert res.monthly_averages[0].observation_days == 30
    assert res.monthly_averages[0].coverage_percentage == 100.0

    assert res.monthly_averages[1].month == "July"
    assert res.monthly_averages[1].average_temperature_celsius == 26.7
    assert res.monthly_averages[1].observation_days == 31
    assert res.monthly_averages[1].coverage_percentage == 100.0

    assert res.monthly_averages[2].month == "August"
    assert res.monthly_averages[2].average_temperature_celsius == 25.2
    assert res.monthly_averages[2].observation_days == 31
    assert res.monthly_averages[2].coverage_percentage == 100.0

    assert res.monthly_averages[3].month == "September"
    assert res.monthly_averages[3].average_temperature_celsius == 25.3
    assert res.monthly_averages[3].observation_days == 30
    assert res.monthly_averages[3].coverage_percentage == 100.0

    # Start date and end date must match selected months
    assert res.start_date == "2026-06-01"
    assert res.end_date == "2026-09-30"

    # Total days: 30 + 31 + 31 + 30 = 122
    assert res.total_observation_days == 122
    assert res.data_coverage_percentage == 100.0

    # Overall average: (30*29.1 + 31*26.7 + 31*25.2 + 30*25.3) / 122
    # = (873.0 + 827.7 + 781.2 + 759.0) / 122 = 3240.9 / 122 = 26.5647... -> 26.56
    assert res.overall_average_temperature_celsius == 26.56


# ---------------------------------------------------------------------------
# Test 14: Current Month Included When >= 90% Coverage (User Prompt Example 2)
# ---------------------------------------------------------------------------
def test_current_month_included_when_over_90_percent(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """If October coverage is >= 90% (e.g. 30 observations out of 31 = 96.8%):
    October -> INCLUDE
    September -> INCLUDE
    August -> INCLUDE
    July -> INCLUDE
    Final calculation: July + August + September + October (exactly 4 months).
    """
    ref_date = date(2026, 10, 30)

    dates: list[str] = []
    temps: list[float] = []

    # July: 31 days @ 26.7
    for d in range(1, 32):
        dates.append(f"2026-07-{d:02d}")
        temps.append(26.7)
    # August: 31 days @ 25.2
    for d in range(1, 32):
        dates.append(f"2026-08-{d:02d}")
        temps.append(25.2)
    # September: 30 days @ 25.3
    for d in range(1, 31):
        dates.append(f"2026-09-{d:02d}")
        temps.append(25.3)
    # October: 30 days @ 27.0 (Coverage = 30/31 = 96.8% >= 90%)
    for d in range(1, 31):
        dates.append(f"2026-10-{d:02d}")
        temps.append(27.0)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Bhopal", "month", duration=4, reference_date=ref_date)

    assert res.status == "SUCCESS"
    assert res.duration == 4
    assert len(res.monthly_averages) == 4

    month_names = [m.month for m in res.monthly_averages]
    assert month_names == ["July", "August", "September", "October"]

    assert res.start_date == "2026-07-01"
    assert res.end_date == "2026-10-31"


# ---------------------------------------------------------------------------
# Test 15: 1 Month Duration with < 90% Current Month
# ---------------------------------------------------------------------------
def test_1_month_selects_previous_complete_month_when_under_90_percent(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """User selects 1 Month when current month < 90%:
    -> selects previous complete month (September).
    """
    ref_date = date(2026, 10, 3)

    dates: list[str] = []
    temps: list[float] = []

    # September: 30 days @ 25.3
    for d in range(1, 31):
        dates.append(f"2026-09-{d:02d}")
        temps.append(25.3)
    # October: 3 days @ 26.8
    for d in range(1, 4):
        dates.append(f"2026-10-{d:02d}")
        temps.append(26.8)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Bhopal", "month", duration=1, reference_date=ref_date)

    assert res.status == "SUCCESS"
    assert res.duration == 1
    assert len(res.monthly_averages) == 1
    assert res.monthly_averages[0].month == "September"
    assert res.monthly_averages[0].average_temperature_celsius == 25.3
    assert res.start_date == "2026-09-01"
    assert res.end_date == "2026-09-30"


# ---------------------------------------------------------------------------
# Test 16: 3 Months Duration with < 90% Current Month
# ---------------------------------------------------------------------------
def test_3_months_selects_previous_3_complete_months(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """User selects 3 Months when current month < 90%:
    -> selects July, August, September.
    """
    ref_date = date(2026, 10, 3)

    dates: list[str] = []
    temps: list[float] = []

    for d in range(1, 32):
        dates.append(f"2026-07-{d:02d}")
        temps.append(26.7)
    for d in range(1, 32):
        dates.append(f"2026-08-{d:02d}")
        temps.append(25.2)
    for d in range(1, 31):
        dates.append(f"2026-09-{d:02d}")
        temps.append(25.3)
    for d in range(1, 4):
        dates.append(f"2026-10-{d:02d}")
        temps.append(26.8)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Bhopal", "month", duration=3, reference_date=ref_date)

    assert res.status == "SUCCESS"
    assert res.duration == 3
    assert len(res.monthly_averages) == 3
    assert [m.month for m in res.monthly_averages] == ["July", "August", "September"]
    assert res.start_date == "2026-07-01"
    assert res.end_date == "2026-09-30"
    assert res.overall_average_temperature_celsius == 25.74


# ---------------------------------------------------------------------------
# Test 17: Week Duration Validation (1, 2, 3 Allowed; 4 and Others Rejected)
# ---------------------------------------------------------------------------
def test_week_duration_validation(service: StatisticsService) -> None:
    """Week period must support ONLY 1, 2, 3 weeks; 4 weeks is rejected."""
    from app.schemas.weather_schema import StatisticsPeriod

    assert service.validate_period_value(StatisticsPeriod.WEEK, 1) == 1
    assert service.validate_period_value(StatisticsPeriod.WEEK, 2) == 2
    assert service.validate_period_value(StatisticsPeriod.WEEK, 3) == 3

    with pytest.raises(ValueError, match="Invalid week duration: 4"):
        service.validate_period_value(StatisticsPeriod.WEEK, 4)

    with pytest.raises(ValueError, match="Invalid week duration: 0"):
        service.validate_period_value(StatisticsPeriod.WEEK, 0)

    with pytest.raises(ValueError, match="Invalid week duration: 5"):
        service.validate_period_value(StatisticsPeriod.WEEK, 5)


# ---------------------------------------------------------------------------
# Test 18: Week Date Range Mapping (1 -> 7d, 2 -> 14d, 3 -> 21d)
# ---------------------------------------------------------------------------
def test_week_date_range_mapping(service: StatisticsService) -> None:
    """1 Week = 7 days, 2 Weeks = 14 days, 3 Weeks = 21 days."""
    ref_date = date(2026, 10, 3)

    s1, e1, days1 = service.get_date_range("week", 1, ref_date)
    assert days1 == 7
    assert s1 == date(2026, 9, 26)
    assert e1 == date(2026, 10, 3)

    s2, e2, days2 = service.get_date_range("week", 2, ref_date)
    assert days2 == 14
    assert s2 == date(2026, 9, 19)
    assert e2 == date(2026, 10, 3)

    s3, e3, days3 = service.get_date_range("week", 3, ref_date)
    assert days3 == 21
    assert s3 == date(2026, 9, 12)
    assert e3 == date(2026, 10, 3)

    with pytest.raises(ValueError, match="Invalid week duration: 4"):
        service.get_date_range("week", 4, ref_date)


# ---------------------------------------------------------------------------
# Test 19: 3 Weeks Historical Calculation
# ---------------------------------------------------------------------------
def test_three_weeks_calculation(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Test 3 Weeks duration calculates pure average across 21 days without monthly breakdown."""
    ref_date = date(2026, 10, 3)
    start_date, end_date, expected_days = service.get_date_range("week", 3, ref_date)
    assert expected_days == 21

    temps = [25.0 + (i % 5) * 0.5 for i in range(21)]
    dates = [str(start_date + timedelta(days=i)) for i in range(21)]

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Bhopal", "week", duration=3, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.duration == 3
    assert res.period_type == "week"
    assert res.start_date == "2026-09-12"
    assert res.end_date == "2026-10-03"
    assert res.observation_days == 21
    assert res.average_temperature_celsius is not None
    assert res.monthly_averages is None
    assert res.daily_records is not None
    assert len(res.daily_records) == 22


# ---------------------------------------------------------------------------
# Test 20: Week Daily Temperature Breakdown & Overall Average Calculation
# ---------------------------------------------------------------------------
def test_week_daily_temperature_breakdown(
    service: StatisticsService, mock_historical_service: MagicMock
) -> None:
    """Test 2 Weeks analysis returns daily temperature breakdown and calculates pure average."""
    ref_date = date(2026, 10, 3)
    start_date, end_date, expected_days = service.get_date_range("week", 2, ref_date)
    assert start_date == date(2026, 9, 19)
    assert end_date == date(2026, 10, 3)

    # 15 days from Sep 19 to Oct 03, with one missing day (Sep 22)
    dates = []
    temps = []
    curr = start_date
    while curr <= end_date:
        d_str = curr.isoformat()
        dates.append(d_str)
        if d_str == "2026-09-22":
            temps.append(None)  # missing
        else:
            temps.append(27.0)
        curr += timedelta(days=1)

    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": dates,
        "temperatures": temps,
    }

    res = service.calculate_average_weather("Indore", "week", duration=2, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.period_type == "week"
    assert res.duration == 2
    assert res.daily_records is not None
    assert len(res.daily_records) == 15

    # Check Sep 19
    r_sep19 = next(r for r in res.daily_records if r.date == "2026-09-19")
    assert r_sep19.formatted_date == "Sep 19"
    assert r_sep19.average_temperature_celsius == 27.0
    assert r_sep19.status == "100%"

    # Check missing Sep 22
    r_sep22 = next(r for r in res.daily_records if r.date == "2026-09-22")
    assert r_sep22.formatted_date == "Sep 22"
    assert r_sep22.average_temperature_celsius is None
    assert r_sep22.status == "Missing"

    # Overall average is computed only from valid daily temperatures (14 observations)
    assert res.observation_days == 14
    assert res.average_temperature_celsius == 27.0



