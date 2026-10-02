"""Unit tests for StatisticsService and Open-Meteo historical weather integration.

Covers the 13 required test scenarios:
1. Indore 1 week
2. Indore 2 weeks
3. Indore 4 weeks
4. Indore 1 month
5. Indore 3 months
6. Indore 6 months
7. Indore 12 months
8. Invalid city
9. Open-Meteo API failure
10. Missing temperature values
11. Empty API response
12. Average calculation
13. Correct date-range calculation
"""

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
from app.services.statistics_service import StatisticsService, subtract_calendar_months


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
# Test 12: Average calculation
# ---------------------------------------------------------------------------
def test_average_calculation() -> None:
    """Test pure average temperature calculation matching user prompt example."""
    calc = AverageTemperatureCalculator()

    # Empty list
    assert calc.calculate_average_temperature([]) is None

    # Prompt example: Daily temperatures: 30, 31, 29, 32, 30 -> Average: 30.4°C
    example_temps = [30.0, 31.0, 29.0, 32.0, 30.0]
    assert calc.calculate_average_temperature(example_temps) == 30.4

    # Direct list of integers
    assert calc.calculate_average_temperature([30, 31, 29, 32, 30]) == 30.4

    # Dict observations
    dict_obs = [{"temperature": 25.0}, {"temperature": None}, {"temperature": 35.0}]
    assert calc.calculate_average_temperature(dict_obs) == 30.0


# ---------------------------------------------------------------------------
# Test 13: Correct date-range calculation
# ---------------------------------------------------------------------------
def test_correct_date_range_calculation(service: StatisticsService) -> None:
    """Test date-range calculations for weeks and calendar months."""
    ref_date = date(2026, 10, 2)

    # Week: 1 week = 7 days, 2 weeks = 14 days, 3 weeks = 21 days, 4 weeks = 28 days
    start_1w, end_1w, days_1w = service.get_date_range("week", 1, ref_date)
    assert days_1w == 7
    assert (end_1w - start_1w).days == 7
    assert start_1w == date(2026, 9, 25)

    start_2w, end_2w, days_2w = service.get_date_range("week", 2, ref_date)
    assert days_2w == 14
    assert (end_2w - start_2w).days == 14
    assert start_2w == date(2026, 9, 18)

    start_3w, end_3w, days_3w = service.get_date_range("week", 3, ref_date)
    assert days_3w == 21
    assert (end_3w - start_3w).days == 21

    start_4w, end_4w, days_4w = service.get_date_range("week", 4, ref_date)
    assert days_4w == 28
    assert (end_4w - start_4w).days == 28
    assert start_4w == date(2026, 9, 4)

    # Month: Calendar month calculations
    start_1m, end_1m, days_1m = service.get_date_range("month", 1, ref_date)
    assert start_1m == date(2026, 9, 2)
    assert days_1m == 30

    start_3m, end_3m, days_3m = service.get_date_range("month", 3, ref_date)
    assert start_3m == date(2026, 7, 2)
    assert days_3m == 92

    start_6m, end_6m, days_6m = service.get_date_range("month", 6, ref_date)
    assert start_6m == date(2026, 4, 2)

    start_12m, end_12m, days_12m = service.get_date_range("month", 12, ref_date)
    assert start_12m == date(2025, 10, 2)
    assert days_12m == 365

    # Month boundary edge case: March 31 minus 1 month in non-leap year (Feb 28)
    assert subtract_calendar_months(date(2023, 3, 31), 1) == date(2023, 2, 28)
    # Leap year (Feb 29)
    assert subtract_calendar_months(date(2024, 3, 31), 1) == date(2024, 2, 29)

    # Year option strictly removed
    with pytest.raises(ValueError, match="The 'year' period option has been removed"):
        service.parse_period("year")


# ---------------------------------------------------------------------------
# Test 1: Indore 1 week
# ---------------------------------------------------------------------------
def test_indore_1_week(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 1 week historical calculation."""
    ref_date = date(2026, 10, 2)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(ref_date - timedelta(days=7 - i)) for i in range(7)],
        "temperatures": [28.0, 29.0, 30.0, 31.0, 29.5, 30.5, 31.0],
    }

    res = service.calculate_average_weather("Indore", "week", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.provider == "open-meteo"
    assert res.period_type == "week"
    assert res.duration == 1
    assert res.observation_days == 7
    assert res.coverage_percentage == 100.0
    assert res.average_temperature_celsius == 29.9


# ---------------------------------------------------------------------------
# Test 2: Indore 2 weeks
# ---------------------------------------------------------------------------
def test_indore_2_weeks(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 2 weeks historical calculation."""
    ref_date = date(2026, 10, 2)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(ref_date - timedelta(days=14 - i)) for i in range(14)],
        "temperatures": [28.0 + (i % 3) for i in range(14)],
    }

    res = service.calculate_average_weather("Indore", "week", duration=2, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.provider == "open-meteo"
    assert res.duration == 2
    assert res.observation_days == 14
    assert res.coverage_percentage == 100.0
    assert res.average_temperature_celsius is not None


# ---------------------------------------------------------------------------
# Test 3: Indore 4 weeks
# ---------------------------------------------------------------------------
def test_indore_4_weeks(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 4 weeks historical calculation."""
    ref_date = date(2026, 10, 2)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(ref_date - timedelta(days=28 - i)) for i in range(28)],
        "temperatures": [27.0 + (i % 4) for i in range(28)],
    }

    res = service.calculate_average_weather("Indore", "week", duration=4, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.duration == 4
    assert res.observation_days == 28
    assert res.coverage_percentage == 100.0


# ---------------------------------------------------------------------------
# Test 4: Indore 1 month
# ---------------------------------------------------------------------------
def test_indore_1_month(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 1 month historical calculation."""
    ref_date = date(2026, 10, 2)
    # 2026-09-02 to 2026-10-02 = 30 days
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(ref_date - timedelta(days=30 - i)) for i in range(30)],
        "temperatures": [26.0 + (i % 5) for i in range(30)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.provider == "open-meteo"
    assert res.period_type == "month"
    assert res.duration == 1
    assert res.observation_days == 30


# ---------------------------------------------------------------------------
# Test 5: Indore 3 months
# ---------------------------------------------------------------------------
def test_indore_3_months(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 3 months historical calculation."""
    ref_date = date(2026, 10, 2)
    # 2026-07-02 to 2026-10-02 = 92 days
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(ref_date - timedelta(days=92 - i)) for i in range(92)],
        "temperatures": [29.8 for _ in range(92)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=3, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.duration == 3
    assert res.observation_days == 92
    assert res.average_temperature_celsius == 29.8


# ---------------------------------------------------------------------------
# Test 6: Indore 6 months
# ---------------------------------------------------------------------------
def test_indore_6_months(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 6 months historical calculation."""
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("month", 6, ref_date)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(start_date + timedelta(days=i)) for i in range(expected_days)],
        "temperatures": [28.0 for _ in range(expected_days)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=6, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.duration == 6
    assert res.observation_days == expected_days


# ---------------------------------------------------------------------------
# Test 7: Indore 12 months
# ---------------------------------------------------------------------------
def test_indore_12_months(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Indore 12 months historical calculation."""
    ref_date = date(2026, 10, 2)
    start_date, end_date, expected_days = service.get_date_range("month", 12, ref_date)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [str(start_date + timedelta(days=i)) for i in range(expected_days)],
        "temperatures": [25.0 for _ in range(expected_days)],
    }

    res = service.calculate_average_weather("Indore", "month", duration=12, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.duration == 12
    assert res.observation_days == expected_days
    assert res.average_temperature_celsius == 25.0


# ---------------------------------------------------------------------------
# Test 8: Invalid city
# ---------------------------------------------------------------------------
def test_invalid_city(service: StatisticsService) -> None:
    """Test invalid city input validations."""
    with pytest.raises(ValueError, match="cannot be empty"):
        service.calculate_average_weather("", "week", 1)

    with pytest.raises(ValueError, match="cannot be empty"):
        service.calculate_average_weather("   ", "week", 1)

    with pytest.raises(ValueError, match="at least 2 characters"):
        service.calculate_average_weather("X", "week", 1)

    with pytest.raises(ValueError, match="contain alphabetic characters"):
        service.calculate_average_weather("12345", "week", 1)


# ---------------------------------------------------------------------------
# Test 9: Open-Meteo API failure
# ---------------------------------------------------------------------------
def test_open_meteo_api_failure(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test Open-Meteo API failure propagation."""
    mock_historical_service.fetch_historical_temperatures.side_effect = WeatherServiceUnavailableError(
        "Open-Meteo API unavailable"
    )

    with pytest.raises(WeatherServiceUnavailableError, match="unavailable"):
        service.calculate_average_weather("Indore", "week", 1)


# ---------------------------------------------------------------------------
# Test 10: Missing temperature values
# ---------------------------------------------------------------------------
def test_missing_temperature_values(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test missing/null temperature values are filtered out without fabricating fake values."""
    ref_date = date(2026, 10, 2)
    # 7 days requested, 5 valid numbers and 2 None values (>70% coverage: 5/7 = 71.4%)
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": ["d1", "d2", "d3", "d4", "d5", "d6", "d7"],
        "temperatures": [30.0, None, 32.0, 28.0, None, 30.0, 30.0],
    }

    res = service.calculate_average_weather("Indore", "week", duration=1, reference_date=ref_date)
    assert res.status == "SUCCESS"
    assert res.observation_days == 5
    # (30 + 32 + 28 + 30 + 30) / 5 = 150 / 5 = 30.0
    assert res.average_temperature_celsius == 30.0


# ---------------------------------------------------------------------------
# Test 11: Empty API response
# ---------------------------------------------------------------------------
def test_empty_api_response(service: StatisticsService, mock_historical_service: MagicMock) -> None:
    """Test empty API response results in INSUFFICIENT_HISTORICAL_DATA without fabricating values."""
    mock_historical_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": [],
        "temperatures": [],
    }

    res = service.calculate_average_weather("Indore", "week", duration=1)
    assert res.status == "INSUFFICIENT_HISTORICAL_DATA"
    assert res.average_temperature_celsius is None
    assert res.observation_days == 0
    assert res.coverage_percentage == 0.0
    assert "Unable to retrieve historical weather data" in res.message
