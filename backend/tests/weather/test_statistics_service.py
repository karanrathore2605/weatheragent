"""Unit tests for StatisticsService and AverageTemperatureCalculator with AccuWeather."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.models.weather_observation import WeatherObservation
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import StatisticsPeriod
from app.services.average_temperature_calculator import AverageTemperatureCalculator
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
    """Fixture providing a mock HistoricalWeatherService (AccuWeather)."""
    service = MagicMock(spec=HistoricalWeatherService)
    return service


@pytest.fixture
def service(mock_historical_service: MagicMock, mock_repo: MagicMock) -> StatisticsService:
    """Fixture providing StatisticsService with mocked AccuWeather historical service."""
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
        source="accuweather",
    )
    return obs


# ---------------------------------------------------------------------------
# AverageTemperatureCalculator tests
# ---------------------------------------------------------------------------

def test_average_temperature_calculator() -> None:
    """Test AverageTemperatureCalculator standalone calculations."""
    calc = AverageTemperatureCalculator()

    # Empty list
    assert calc.calculate_average_temperature([]) is None

    # Valid observations
    obs_list = [
        create_observation(temp=30.0),
        create_observation(temp=32.0),
        create_observation(temp=31.0),
    ]
    assert calc.calculate_average_temperature(obs_list) == 31.0

    # With None / null temperatures ignored
    dict_obs = [
        {"temperature": 25.0},
        {"temperature": None},
        {"temperature": 35.0},
    ]
    assert calc.calculate_average_temperature(dict_obs) == 30.0


# ---------------------------------------------------------------------------
# City validation
# ---------------------------------------------------------------------------

def test_validate_city_input(service: StatisticsService) -> None:
    """Test city name validation in StatisticsService."""
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
# Year option removed
# ---------------------------------------------------------------------------

def test_year_option_removed(service: StatisticsService) -> None:
    """Test that 'year' period option is strictly rejected."""
    with pytest.raises(ValueError, match="The 'year' period option has been removed"):
        service.parse_period("year")

    with pytest.raises(ValueError, match="The 'year' period option has been removed"):
        service.parse_period("YEAR")

    with pytest.raises(ValueError, match="Supported periods: week, month"):
        service.parse_period("century")


def test_parse_valid_periods(service: StatisticsService) -> None:
    """Test parsing supported periods 'week' and 'month'."""
    assert service.parse_period("week") == StatisticsPeriod.WEEK
    assert service.parse_period("WEEK") == StatisticsPeriod.WEEK
    assert service.parse_period("month") == StatisticsPeriod.MONTH
    assert service.parse_period("MONTH") == StatisticsPeriod.MONTH


# ---------------------------------------------------------------------------
# Duration validation: Week (1-4) & Month (1-12)
# ---------------------------------------------------------------------------

def test_validate_week_durations(service: StatisticsService) -> None:
    """Test duration validation for week: 1, 2, 3, 4."""
    for d in [1, 2, 3, 4]:
        assert service.validate_period_value(StatisticsPeriod.WEEK, d) == d

    with pytest.raises(ValueError, match="Supported durations for week"):
        service.validate_period_value(StatisticsPeriod.WEEK, 0)

    with pytest.raises(ValueError, match="Supported durations for week"):
        service.validate_period_value(StatisticsPeriod.WEEK, 5)


def test_validate_month_durations(service: StatisticsService) -> None:
    """Test duration validation for month: 1 through 12."""
    for d in range(1, 13):
        assert service.validate_period_value(StatisticsPeriod.MONTH, d) == d

    with pytest.raises(ValueError, match="Supported durations for month"):
        service.validate_period_value(StatisticsPeriod.MONTH, 0)

    with pytest.raises(ValueError, match="Supported durations for month"):
        service.validate_period_value(StatisticsPeriod.MONTH, 13)


# ---------------------------------------------------------------------------
# Week requests: 1, 2, 3, 4 weeks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("weeks,expected_days", [(1, 7), (2, 14), (3, 21), (4, 28)])
def test_week_requests(
    service: StatisticsService,
    mock_historical_service: MagicMock,
    weeks: int,
    expected_days: int,
) -> None:
    """Test 1, 2, 3, and 4 week calculations."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    expected_hours = expected_days * 24

    obs_count = int(expected_hours * 0.8)
    base_time = ref - timedelta(days=expected_days)
    observations = [
        create_observation(dt=base_time + timedelta(hours=i), temp=20.0 + (i % 10))
        for i in range(obs_count)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"city": "Indore", "formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=weeks, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.provider == "accuweather"
    assert res.period_type == "week"
    assert res.duration == weeks
    assert res.data_coverage["complete"] is True
    assert res.average_temperature_celsius is not None
    assert res.coverage.complete is True


# ---------------------------------------------------------------------------
# Month requests: 1 through 12 months
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("months", list(range(1, 13)))
def test_month_requests(
    service: StatisticsService,
    mock_historical_service: MagicMock,
    months: int,
) -> None:
    """Test 1 through 12 month calculations."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    start_date, end_date, expected_obs = service.get_date_range("month", period_value=months, reference_date=ref)

    obs_count = int(expected_obs * 0.75)
    observations = [
        create_observation(dt=start_date + timedelta(hours=i), temp=22.0 + (i % 8))
        for i in range(obs_count)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"city": "Indore", "formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "month", period_value=months, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.city == "Indore"
    assert res.provider == "accuweather"
    assert res.period_type == "month"
    assert res.duration == months
    assert res.data_coverage["complete"] is True
    assert res.average_temperature_celsius is not None


# ---------------------------------------------------------------------------
# Incomplete historical coverage
# ---------------------------------------------------------------------------

def test_incomplete_historical_coverage(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test incomplete AccuWeather coverage returns structured INSUFFICIENT_HISTORICAL_DATA."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Expected for 1 week is 168 hours. Only 24 hours available (~14.3% < 70%).
    observations = [
        create_observation(dt=ref - timedelta(hours=i), temp=25.0)
        for i in range(24)
    ]
    mock_historical_service.fetch_and_get_observations.return_value = (
        observations,
        {"city": "Indore", "formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=1, reference_date=ref)

    assert res.status == "INSUFFICIENT_HISTORICAL_DATA"
    assert res.city == "Indore"
    assert res.provider == "accuweather"
    assert res.data_coverage["complete"] is False
    assert res.coverage.complete is False
    assert res.average_temperature_celsius is None
    assert "Historical weather data is not available" in res.message


# ---------------------------------------------------------------------------
# AccuWeather API failure propagation
# ---------------------------------------------------------------------------

def test_accuweather_api_failure_propagates(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that AccuWeather API failure raises proper exception."""
    mock_historical_service.fetch_and_get_observations.side_effect = WeatherServiceUnavailableError(
        "AccuWeather service is temporarily unavailable."
    )

    with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
        service.calculate_average_weather("Indore", "week", period_value=1)


def test_accuweather_auth_failure_propagates(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that AccuWeather 401/403 auth error propagates."""
    mock_historical_service.fetch_and_get_observations.side_effect = WeatherAuthenticationError(
        "AccuWeather service authentication failed."
    )

    with pytest.raises(WeatherAuthenticationError, match="authentication failed"):
        service.calculate_average_weather("Indore", "week", period_value=1)


# ---------------------------------------------------------------------------
# No fake data is generated
# ---------------------------------------------------------------------------

def test_no_fake_data_is_generated_on_empty(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test that when 0 observations are returned, no fake numbers are fabricated."""
    mock_historical_service.fetch_and_get_observations.return_value = (
        [],
        {"city": "Indore", "formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "month", period_value=12)

    assert res.status == "INSUFFICIENT_HISTORICAL_DATA"
    assert res.provider == "accuweather"
    assert res.data_coverage["complete"] is False
    assert res.coverage.complete is False
    assert res.average_temperature_celsius is None
    assert res.statistics is None


def test_calculations_ignore_null_values_without_fabrication(
    service: StatisticsService,
    mock_historical_service: MagicMock,
) -> None:
    """Test calculator strictly averages real values and ignores nulls."""
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
        {"city": "Indore", "formatted_address": "Indore, Madhya Pradesh, India"},
    )

    res = service.calculate_average_weather("Indore", "week", period_value=1, reference_date=ref)

    assert res.status == "SUCCESS"
    assert res.provider == "accuweather"
    assert res.average_temperature_celsius == 25.0
    assert res.data_coverage["complete"] is True
