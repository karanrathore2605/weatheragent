"""Tests for Monthly Weather Report calculations, LLM summarization, and API endpoints."""

import calendar
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.clients.weather_client import CityNotFoundError, WeatherTimeoutError
from app.main import app
from app.schemas.monthly_report_schema import MonthlyWeatherReportResponse, WeeklyPeriodReport
from app.services.monthly_report_service import MonthlyReportService, parse_month_and_year
from app.services.weekly_calculation_service import WeeklyCalculationResult, WeeklyCalculationService


# ==============================================================================
# Unit Tests: Month Parsing & Weekly Periods
# ==============================================================================

def test_parse_month_and_year_valid():
    """Verify various string and integer formats for month and year parsing."""
    assert parse_month_and_year("August 2026") == (2026, 8)
    assert parse_month_and_year("Aug 2026") == (2026, 8)
    assert parse_month_and_year("2026-08") == (2026, 8)
    assert parse_month_and_year("2026/08") == (2026, 8)
    assert parse_month_and_year("July 2026") == (2026, 7)
    assert parse_month_and_year("September 2026") == (2026, 9)
    assert parse_month_and_year("August", year_input=2026) == (2026, 8)
    assert parse_month_and_year(8, year_input=2026) == (2026, 8)
    assert parse_month_and_year("8", year_input=2026) == (2026, 8)


def test_parse_month_and_year_invalid():
    """Verify invalid month names or ranges raise ValueError."""
    with pytest.raises(ValueError):
        parse_month_and_year("InvalidMonth 2026")

    with pytest.raises(ValueError):
        parse_month_and_year(13, 2026)

    with pytest.raises(ValueError):
        parse_month_and_year("2026-15")


def test_get_month_weekly_periods_31_days():
    """Verify August (31 days) divides into Week 1-4 and Remaining Days (Aug 29 - Aug 31)."""
    periods = WeeklyCalculationService.get_month_weekly_periods(2026, 8)
    assert len(periods) == 5

    assert periods[0]["week"] == "Week 1"
    assert periods[0]["date_range"] == "Aug 1 - Aug 7"
    assert periods[0]["expected_days"] == 7

    assert periods[1]["week"] == "Week 2"
    assert periods[1]["date_range"] == "Aug 8 - Aug 14"
    assert periods[1]["expected_days"] == 7

    assert periods[2]["week"] == "Week 3"
    assert periods[2]["date_range"] == "Aug 15 - Aug 21"
    assert periods[2]["expected_days"] == 7

    assert periods[3]["week"] == "Week 4"
    assert periods[3]["date_range"] == "Aug 22 - Aug 28"
    assert periods[3]["expected_days"] == 7

    # Remaining days must NOT be called Week 5
    assert periods[4]["week"] == "Remaining Days"
    assert periods[4]["date_range"] == "Aug 29 - Aug 31"
    assert periods[4]["expected_days"] == 3


def test_get_month_weekly_periods_30_days():
    """Verify September (30 days) divides into Week 1-4 and Remaining Days (Sep 29 - Sep 30)."""
    periods = WeeklyCalculationService.get_month_weekly_periods(2026, 9)
    assert len(periods) == 5
    assert periods[4]["week"] == "Remaining Days"
    assert periods[4]["date_range"] == "Sep 29 - Sep 30"
    assert periods[4]["expected_days"] == 2


def test_get_month_weekly_periods_28_days_non_leap():
    """Verify February in non-leap year (28 days) has NO remaining days."""
    periods = WeeklyCalculationService.get_month_weekly_periods(2025, 2)
    assert len(periods) == 4
    week_names = [p["week"] for p in periods]
    assert "Remaining Days" not in week_names
    assert "Week 5" not in week_names
    assert periods[3]["date_range"] == "Feb 22 - Feb 28"


def test_get_month_weekly_periods_29_days_leap():
    """Verify February in leap year (29 days) has Remaining Days (Feb 29 - Feb 29)."""
    periods = WeeklyCalculationService.get_month_weekly_periods(2028, 2)
    assert len(periods) == 5
    assert periods[4]["week"] == "Remaining Days"
    assert periods[4]["date_range"] == "Feb 29 - Feb 29"
    assert periods[4]["expected_days"] == 1


# ==============================================================================
# Unit Tests: WeeklyCalculationService
# ==============================================================================

def test_weekly_calculation_service_normal():
    """Verify backend calculates weekly averages deterministically from daily observations."""
    mock_hist_service = MagicMock()
    # Mock August 2026 with 31 days of data: 25.0 to 28.0
    mock_dates = [f"2026-08-{d:02d}" for d in range(1, 32)]
    # Week 1: all 26.0 -> avg 26.0
    # Week 2: all 25.0 -> avg 25.0
    # Week 3: all 27.0 -> avg 27.0
    # Week 4: all 24.0 -> avg 24.0
    # Remaining: all 25.0 -> avg 25.0
    mock_temps = (
        [26.0] * 7 +
        [25.0] * 7 +
        [27.0] * 7 +
        [24.0] * 7 +
        [25.0] * 3
    )
    mock_hist_service.fetch_historical_temperatures.return_value = {
        "city": "Indore",
        "dates": mock_dates,
        "temperatures": mock_temps,
        "location": {"city": "Indore", "admin1": "Madhya Pradesh", "country": "India"},
    }

    service = WeeklyCalculationService(historical_service=mock_hist_service)
    result = service.calculate_monthly_weekly_averages("Indore", 2026, 8)

    assert result.is_available is True
    assert result.city_display == "Indore, Madhya Pradesh"
    assert result.month_display == "August 2026"
    assert len(result.weekly_reports) == 5

    assert result.weekly_reports[0].week == "Week 1"
    assert result.weekly_reports[0].average_temperature == 26.0
    assert result.weekly_reports[0].is_complete is True

    assert result.weekly_reports[1].week == "Week 2"
    assert result.weekly_reports[1].average_temperature == 25.0

    assert result.weekly_reports[2].week == "Week 3"
    assert result.weekly_reports[2].average_temperature == 27.0

    assert result.weekly_reports[3].week == "Week 4"
    assert result.weekly_reports[3].average_temperature == 24.0

    assert result.weekly_reports[4].week == "Remaining Days"
    assert result.weekly_reports[4].average_temperature == 25.0

    assert result.highest_week["week"] == "Week 3"
    assert result.highest_week["average_temperature"] == 27.0

    assert result.lowest_week["week"] == "Week 4"
    assert result.lowest_week["average_temperature"] == 24.0


def test_weekly_calculation_service_incomplete_days():
    """Verify that missing observations are not replaced by 0 and marked incomplete."""
    mock_hist_service = MagicMock()
    mock_dates = [f"2026-08-{d:02d}" for d in range(1, 32)]
    # Week 1: 5 valid days (20, 22, 24, 26, 28) and 2 None days -> avg 24.0
    w1_temps = [20.0, 22.0, 24.0, 26.0, 28.0, None, None]
    mock_temps = w1_temps + [25.0] * 24

    mock_hist_service.fetch_historical_temperatures.return_value = {
        "city": "Bhopal",
        "dates": mock_dates,
        "temperatures": mock_temps,
        "location": {"city": "Bhopal", "admin1": "Madhya Pradesh"},
    }

    service = WeeklyCalculationService(historical_service=mock_hist_service)
    result = service.calculate_monthly_weekly_averages("Bhopal", 2026, 8)

    w1 = result.weekly_reports[0]
    assert w1.observation_count == 5
    assert w1.expected_days == 7
    assert w1.is_complete is False
    assert w1.average_temperature == 24.0
    assert "Incomplete data (5/7 days)" in w1.note


def test_weekly_calculation_service_completely_unavailable():
    """Verify that if historical provider returns 0 observations, is_available is False."""
    mock_hist_service = MagicMock()
    mock_hist_service.fetch_historical_temperatures.return_value = {
        "city": "Unknown",
        "dates": [],
        "temperatures": [],
        "location": {},
    }

    service = WeeklyCalculationService(historical_service=mock_hist_service)
    result = service.calculate_monthly_weekly_averages("Unknown", 2026, 8)

    assert result.is_available is False
    assert result.message == "Historical weather data is currently unavailable for the selected period."


# ==============================================================================
# Unit Tests: MonthlyReportService (Groq Summary Integration & Email Structure)
# ==============================================================================

def test_monthly_report_service_success():
    """Verify that MonthlyReportService coordinates calculation, Groq summary, and email structure."""
    mock_calc_service = MagicMock()
    weekly_reports = [
        WeeklyPeriodReport(week="Week 1", date_range="Aug 1 - Aug 7", start_date="2026-08-01", end_date="2026-08-07", average_temperature=26.4, observation_count=7, expected_days=7, is_complete=True),
        WeeklyPeriodReport(week="Week 2", date_range="Aug 8 - Aug 14", start_date="2026-08-08", end_date="2026-08-14", average_temperature=25.8, observation_count=7, expected_days=7, is_complete=True),
        WeeklyPeriodReport(week="Week 3", date_range="Aug 15 - Aug 21", start_date="2026-08-15", end_date="2026-08-21", average_temperature=24.9, observation_count=7, expected_days=7, is_complete=True),
        WeeklyPeriodReport(week="Week 4", date_range="Aug 22 - Aug 28", start_date="2026-08-22", end_date="2026-08-28", average_temperature=25.6, observation_count=7, expected_days=7, is_complete=True),
        WeeklyPeriodReport(week="Remaining Days", date_range="Aug 29 - Aug 31", start_date="2026-08-29", end_date="2026-08-31", average_temperature=25.2, observation_count=3, expected_days=3, is_complete=True),
    ]
    mock_calc_service.calculate_monthly_weekly_averages.return_value = WeeklyCalculationResult(
        city_display="Indore, Madhya Pradesh",
        city_name="Indore",
        year=2026,
        month_number=8,
        month_name="August",
        month_display="August 2026",
        weekly_reports=weekly_reports,
        is_available=True,
        highest_week={"week": "Week 1", "date_range": "Aug 1 - Aug 7", "average_temperature": 26.4},
        lowest_week={"week": "Week 3", "date_range": "Aug 15 - Aug 21", "average_temperature": 24.9},
        pattern_hint="Relatively stable temperatures",
        total_valid_observations=31,
        expected_month_days=31,
    )

    mock_llm_service = MagicMock()
    mock_llm_service.generate_monthly_report_summary.return_value = (
        "Indore experienced relatively stable temperatures during August 2026. "
        "The highest weekly average temperature was 26.4°C during Week 1, while the lowest was 24.9°C during Week 3."
    )

    service = MonthlyReportService(calculation_service=mock_calc_service, llm_service=mock_llm_service)
    response = service.generate_report("Indore", "August 2026")

    assert response.status == "SUCCESS"
    assert response.city == "Indore, Madhya Pradesh"
    assert response.month == "August 2026"
    assert len(response.weekly_averages) == 5
    assert "26.4°C during Week 1" in response.summary
    assert response.email_payload is not None
    assert len(response.email_payload["weekly_table"]) == 5


def test_monthly_report_service_unavailable():
    """Verify that if calculation returns unavailable, Groq is NOT called."""
    mock_calc_service = MagicMock()
    mock_calc_service.calculate_monthly_weekly_averages.return_value = WeeklyCalculationResult(
        city_display="Indore, Madhya Pradesh",
        city_name="Indore",
        year=2026,
        month_number=8,
        month_name="August",
        month_display="August 2026",
        weekly_reports=[],
        is_available=False,
        highest_week=None,
        lowest_week=None,
        pattern_hint=None,
        total_valid_observations=0,
        expected_month_days=31,
        message="Historical weather data is currently unavailable for the selected period.",
    )
    mock_llm_service = MagicMock()

    service = MonthlyReportService(calculation_service=mock_calc_service, llm_service=mock_llm_service)
    response = service.generate_report("Indore", "August 2026")

    assert response.status == "UNAVAILABLE"
    assert response.message == "Historical weather data is currently unavailable for the selected period."
    assert response.summary is None
    # Verify LLM was NOT invoked
    mock_llm_service.generate_monthly_report_summary.assert_not_called()


# ==============================================================================
# Integration Tests: Router HTTP Endpoints
# ==============================================================================

@pytest.fixture
def client():
    return TestClient(app)


def test_router_get_monthly_report_success(client):
    """Test GET /api/v1/weather/report/monthly endpoint with valid city and month."""
    with patch("app.services.monthly_report_service.WeeklyCalculationService.calculate_monthly_weekly_averages") as mock_calc, \
         patch("app.services.monthly_report_service.LLMService.generate_monthly_report_summary") as mock_llm:

        weekly_reports = [
            WeeklyPeriodReport(week="Week 1", date_range="Aug 1 - Aug 7", start_date="2026-08-01", end_date="2026-08-07", average_temperature=26.4, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 2", date_range="Aug 8 - Aug 14", start_date="2026-08-08", end_date="2026-08-14", average_temperature=25.8, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 3", date_range="Aug 15 - Aug 21", start_date="2026-08-15", end_date="2026-08-21", average_temperature=24.9, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 4", date_range="Aug 22 - Aug 28", start_date="2026-08-22", end_date="2026-08-28", average_temperature=25.6, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Remaining Days", date_range="Aug 29 - Aug 31", start_date="2026-08-29", end_date="2026-08-31", average_temperature=25.2, observation_count=3, expected_days=3, is_complete=True),
        ]
        mock_calc.return_value = WeeklyCalculationResult(
            city_display="Indore, Madhya Pradesh",
            city_name="Indore",
            year=2026,
            month_number=8,
            month_name="August",
            month_display="August 2026",
            weekly_reports=weekly_reports,
            is_available=True,
            highest_week={"week": "Week 1", "date_range": "Aug 1 - Aug 7", "average_temperature": 26.4},
            lowest_week={"week": "Week 3", "date_range": "Aug 15 - Aug 21", "average_temperature": 24.9},
            pattern_hint="Relatively stable temperatures",
            total_valid_observations=31,
            expected_month_days=31,
        )
        mock_llm.return_value = "Indore experienced relatively stable temperatures during August 2026."

        response = client.get("/api/v1/weather/report/monthly", params={"city": "Indore", "month": "August 2026"})
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Indore, Madhya Pradesh"
        assert data["month"] == "August 2026"
        assert len(data["weekly_averages"]) == 5
        assert data["weekly_averages"][0]["average_temperature"] == 26.4
        assert data["weekly_averages"][4]["week"] == "Remaining Days"
        assert data["summary"] == "Indore experienced relatively stable temperatures during August 2026."


def test_router_get_monthly_report_empty_city(client):
    """Test GET /api/v1/weather/report/monthly with empty city returns 400."""
    response = client.get("/api/v1/weather/report/monthly", params={"city": "  ", "month": "August 2026"})
    assert response.status_code == 400


def test_router_get_monthly_report_city_not_found(client):
    """Test GET /api/v1/weather/report/monthly with non-existent city returns 404."""
    with patch("app.services.monthly_report_service.WeeklyCalculationService.calculate_monthly_weekly_averages") as mock_calc:
        mock_calc.side_effect = CityNotFoundError("City 'NonExistentCityXYZ' not found.")
        response = client.get("/api/v1/weather/report/monthly", params={"city": "NonExistentCityXYZ", "month": "August 2026"})
        assert response.status_code == 404


def test_router_post_monthly_report(client):
    """Test POST /api/v1/weather/report/monthly endpoint with JSON body."""
    with patch("app.services.monthly_report_service.WeeklyCalculationService.calculate_monthly_weekly_averages") as mock_calc, \
         patch("app.services.monthly_report_service.LLMService.generate_monthly_report_summary") as mock_llm:

        weekly_reports = [
            WeeklyPeriodReport(week="Week 1", date_range="Jul 1 - Jul 7", start_date="2026-07-01", end_date="2026-07-07", average_temperature=26.6, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 2", date_range="Jul 8 - Jul 14", start_date="2026-07-08", end_date="2026-07-14", average_temperature=27.4, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 3", date_range="Jul 15 - Jul 21", start_date="2026-07-15", end_date="2026-07-21", average_temperature=27.3, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Week 4", date_range="Jul 22 - Jul 28", start_date="2026-07-22", end_date="2026-07-28", average_temperature=25.8, observation_count=7, expected_days=7, is_complete=True),
            WeeklyPeriodReport(week="Remaining Days", date_range="Jul 29 - Jul 31", start_date="2026-07-29", end_date="2026-07-31", average_temperature=26.3, observation_count=3, expected_days=3, is_complete=True),
        ]
        mock_calc.return_value = WeeklyCalculationResult(
            city_display="Bhopal, Madhya Pradesh",
            city_name="Bhopal",
            year=2026,
            month_number=7,
            month_name="July",
            month_display="July 2026",
            weekly_reports=weekly_reports,
            is_available=True,
            highest_week={"week": "Week 2", "date_range": "Jul 8 - Jul 14", "average_temperature": 27.4},
            lowest_week={"week": "Week 4", "date_range": "Jul 22 - Jul 28", "average_temperature": 25.8},
            pattern_hint="Moderate temperature consistency",
            total_valid_observations=31,
            expected_month_days=31,
        )
        mock_llm.return_value = "Bhopal experienced moderate temperatures in July 2026."

        response = client.post("/api/v1/weather/report/monthly", json={"city": "Bhopal", "month": "July 2026"})
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Bhopal, Madhya Pradesh"
        assert data["month"] == "July 2026"
        assert len(data["weekly_averages"]) == 5
