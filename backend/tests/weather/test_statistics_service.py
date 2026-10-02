"""Unit tests for StatisticsService covering all required business rules and periods."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import CityNotFoundError, WeatherServiceUnavailableError
from app.models.weather_observation import WeatherObservation
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import StatisticsPeriod
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.statistics_service import StatisticsService


@pytest.fixture
def mock_repo() -> MagicMock:
    """Fixture providing a mock WeatherObservationRepository."""
    repo = MagicMock(spec=WeatherObservationRepository)
    repo.check_available_data_range.return_value = (
        datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    return repo


@pytest.fixture
def mock_historical_service() -> MagicMock:
    """Fixture providing a mock HistoricalWeatherService (mocking Google Weather API)."""
    service = MagicMock(spec=HistoricalWeatherService)
    return service


@pytest.fixture
def service(mock_historical_service: MagicMock, mock_repo: MagicMock) -> StatisticsService:
    """Fixture providing StatisticsService with mocked Google historical service."""
    return StatisticsService(
        historical_service=mock_historical_service,
        repository=mock_repo,
        min_coverage=70.0,
    )


def create_observation(
    city: str = "Indore",
    dt: datetime = None,
    temp: float = 25.0,
    feels: float = 27.0,
    humidity: float = 60.0,
    wind: float = 10.0,
    precip: float = 1.0,
) -> WeatherObservation:
    """Helper creating mock WeatherObservation instances."""
    obs = WeatherObservation(
        id=1,
        city=city,
        latitude=22.7,
        longitude=75.8,
        observed_at=dt or datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature=temp,
        feels_like_temperature=feels,
        humidity=humidity,
        precipitation=precip,
        wind_speed=wind,
        pressure=1012.0,
        weather_condition="Clear",
        source="google",
    )
    return obs


# ---------------------------------------------------------------------------
# Requirement 11: Invalid city validation
# ---------------------------------------------------------------------------
def test_validate_city_input(service: StatisticsService) -> None:
    """Test city name validation in StatisticsService (Requirement 11)."""
    assert service.validate_city_input("Indore") == "Indore"
    assert service.validate_city_input("  new york  ") == "New York"

    with pytest.raises(ValueError, match="cannot be empty"):
        service.validate_city_input("")

    with pytest.raises(ValueError, match="cannot be empty"):
        service.validate_city_input("   ")

    with pytest.raises(ValueError, match="at least 2 characters"):
        service.validate_city_input("A")

    with pytest.raises(ValueError, match="contain alphabetic characters"):
        service.validate_city_input("12345")


# ---------------------------------------------------------------------------
# Requirement 8: Year option is removed
# ---------------------------------------------------------------------------
def test_year_option_removed(service: StatisticsService) -> None:
    """Test that 'year' period option is strictly rejected (Requirement 8)."""
    with pytest.raises(ValueError, match="The 'year' period option has been removed"):
        service.parse_period("year")

    with pytest.raises(ValueError, match="The 'year' period option has been removed"):
        service.parse_period("YEAR")

    # Also verify unsupported periods
    with pytest.raises(ValueError, match="Supported periods: week, month"):
        service.parse_period("century")


def test_parse_valid_periods(service: StatisticsService) -> None:
    """Test parsing supported periods 'week' and 'month'."""
    assert service.parse_period("week") == StatisticsPeriod.WEEK
    assert service.parse_period("WEEK") == StatisticsPeriod.WEEK
    assert service.parse_period("month") == StatisticsPeriod.MONTH
    assert service.parse_period("MONTH") == StatisticsPeriod.MONTH


def test_validate_period_durations(service: StatisticsService) -> None:
    """Test duration validation for week and month."""
    # Week supports 1, 2, 3
    assert service.validate_period_value(StatisticsPeriod.WEEK, 1) == 1
    assert service.validate_period_value(StatisticsPeriod.WEEK, 2) == 2
    assert service.validate_period_value(StatisticsPeriod.WEEK, 3) == 3
    with pytest.raises(ValueError, match="Supported durations for week: 1, 2, or 3"):
        service.validate_period_value(StatisticsPeriod.WEEK, 4)

    # Month supports 1, 2, 3, 4
    assert service.validate_period_value(StatisticsPeriod.MONTH, 1) == 1
    assert service.validate_period_value(StatisticsPeriod.MONTH, 2) == 2
    assert service.validate_period_value(StatisticsPeriod.MONTH, 3) == 3
    assert service.validate_period_value(StatisticsPeriod.MONTH, 4) == 4
    with pytest.raises(ValueError, match="Supported durations for month: 1, 2, 3, or 4"):
        service.validate_period_value(StatisticsPeriod.MONTH, 5)


# ---------------------------------------------------------------------------
# Requirements 1, 2, 3: Week requests (1-week, 2-week, 3-week)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("weeks,expected_days", [(1, 7), (2, 14), (3, 21)])
def test_week_requests(
    service: StatisticsService,
    mock_historical_service: MagicMock,
    weeks: int,
    expected_days: int,
) -> None:
    """Test 1-week, 2-week, and 3-week requests (Requirements 1, 2, 3)."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    expected_hours = expected_days * 24

    # Provide observations for 80% coverage
    obs_count = int(expected_hours * 0.8)
    base_time = ref - timedelta(days=expected_days)
    observations = [
        create_observation(dt=base_time + timedelta(hours=i), temp=20.0 + (i % 10))
        for i in range(obs_count)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=weeks, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.period_type == "week"
    assert res.period_value == weeks
    assert res.coverage.complete is True
    assert res.statistics is not None
    assert res.statistics.average_temperature is not None
    assert res.statistics.minimum_temperature == 20.0
    assert res.statistics.maximum_temperature == 29.0
    assert res.average_temperature == res.statistics.average_temperature


# ---------------------------------------------------------------------------
# Requirements 4, 5, 6, 7: Month requests (1-month, 2-month, 3-month, 4-month)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("months", [1, 2, 3, 4])
def test_month_requests(
    service: StatisticsService,
    mock_historical_service: MagicMock,
    months: int,
) -> None:
    """Test 1-month, 2-month, 3-month, and 4-month requests (Requirements 4, 5, 6, 7)."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    start_date, end_date, expected_obs = service.get_date_range("month", period_value=months, reference_date=ref)

    obs_count = int(expected_obs * 0.75)
    observations = [
        create_observation(dt=start_date + timedelta(hours=i), temp=22.0 + (i % 8))
        for i in range(obs_count)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "month", period_value=months, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.period_type == "month"
    assert res.period_value == months
    assert res.coverage.complete is True
    assert res.statistics is not None
    assert res.statistics.average_temperature is not None


# ---------------------------------------------------------------------------
# Requirement 9: Incomplete historical coverage
# ---------------------------------------------------------------------------
def test_incomplete_historical_coverage(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that incomplete coverage returns structured INSUFFICIENT_HISTORICAL_DATA (Requirement 9)."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Expected for 1 week is 168 hours. Only 24 hours available (~14.3% coverage < 70%).
    observations = [
        create_observation(dt=ref - timedelta(hours=i), temp=25.0)
        for i in range(24)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=1, reference_date=ref)

    assert res.status == "INSUFFICIENT_HISTORICAL_DATA"
    assert res.city == "Indore"
    assert res.coverage.complete is False
    assert res.statistics is None
    assert res.average_temperature is None
    assert "Not enough historical weather data" in res.message or "not enough" in res.message.lower()


# ---------------------------------------------------------------------------
# Requirement 10: Google API failure
# ---------------------------------------------------------------------------
def test_google_api_failure_propagates(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that Google API failure raises proper exception (Requirement 10)."""
    mock_historical_service.fetch_and_get_observations.side_effect = WeatherServiceUnavailableError(
        "Weather service provider temporarily unavailable."
    )

    with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
        service.calculate_average_weather("Indore", "week", period_value=1)


# ---------------------------------------------------------------------------
# Requirement 12: No fake data is generated
# ---------------------------------------------------------------------------
def test_no_fake_data_is_generated_on_empty(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that when 0 observations are returned, no fake numbers are fabricated (Requirement 12)."""
    mock_historical_service.fetch_and_get_observations.return_value = (
        [],
        {"formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "month", period_value=4)

    assert res.status == "INSUFFICIENT_HISTORICAL_DATA"
    assert res.coverage.complete is False
    assert res.statistics is None
    assert res.average_temperature is None
    assert res.minimum_temperature is None
    assert res.maximum_temperature is None


def test_calculations_ignore_null_values_without_fabrication(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test deterministic calculator strictly averages real values and ignores nulls (Requirement 12)."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    base_time = ref - timedelta(days=7)
    observations = []

    # 130 observations (>70% of 168)
    for i in range(130):
        if i % 2 == 0:
            obs = create_observation(
                dt=base_time + timedelta(hours=i),
                temp=20.0,
                feels=None,
                humidity=None,
                wind=None,
                precip=None,
            )
        else:
            obs = create_observation(
                dt=base_time + timedelta(hours=i),
                temp=30.0,
                feels=32.0,
                humidity=80.0,
                wind=14.0,
                precip=2.0,
            )
        observations.append(obs)

    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=1, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.statistics.average_temperature == 25.0
    assert res.statistics.minimum_temperature == 20.0
    assert res.statistics.maximum_temperature == 30.0
    assert res.statistics.average_feels_like_temperature == 32.0
    assert res.statistics.average_humidity == 80.0
    assert res.statistics.average_wind_speed == 14.0
    assert res.statistics.total_precipitation == 130.0  # 65 * 2.0
