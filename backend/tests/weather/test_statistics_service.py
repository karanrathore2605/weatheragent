"""Unit tests for StatisticsService deterministic calculations, validation, and coverage checks."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from app.models.weather_observation import WeatherObservation
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import StatisticsPeriod
from app.services.statistics_service import StatisticsService


@pytest.fixture
def mock_repo() -> MagicMock:
    """Fixture providing a mock WeatherObservationRepository."""
    repo = MagicMock(spec=WeatherObservationRepository)
    repo.check_available_data_range.return_value = (
        datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> StatisticsService:
    """Fixture providing StatisticsService with min_coverage=70.0%."""
    return StatisticsService(repository=mock_repo, min_coverage=70.0)


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


def test_parse_period(service: StatisticsService) -> None:
    """Test parsing and validating aggregation periods."""
    assert service.parse_period("week") == StatisticsPeriod.WEEK
    assert service.parse_period("MONTH") == StatisticsPeriod.MONTH
    assert service.parse_period("year") == StatisticsPeriod.YEAR

    with pytest.raises(ValueError, match="Supported periods"):
        service.parse_period("decade")

    with pytest.raises(ValueError, match="Supported periods"):
        service.parse_period("invalid")


def test_get_date_range_week() -> None:
    """Test calendar week bounds calculation."""
    # 2026-10-02 is a Friday
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    start, end, expected = StatisticsService.get_date_range(StatisticsPeriod.WEEK, ref)

    # Monday of that week: 2026-09-28
    assert start.strftime("%Y-%m-%d") == "2026-09-28"
    assert start.hour == 0 and start.minute == 0 and start.second == 0
    # Sunday of that week: 2026-10-04
    assert end.strftime("%Y-%m-%d") == "2026-10-04"
    assert end.hour == 23 and end.minute == 59 and end.second == 59
    assert expected == 168


def test_get_date_range_month() -> None:
    """Test calendar month bounds calculation."""
    ref = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    start, end, expected = StatisticsService.get_date_range(StatisticsPeriod.MONTH, ref)

    assert start.strftime("%Y-%m-%d") == "2026-10-01"
    assert end.strftime("%Y-%m-%d") == "2026-10-31"
    assert expected == 31 * 24


def test_get_date_range_year() -> None:
    """Test calendar year bounds calculation."""
    ref = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    start, end, expected = StatisticsService.get_date_range(StatisticsPeriod.YEAR, ref)

    assert start.strftime("%Y-%m-%d") == "2026-01-01"
    assert end.strftime("%Y-%m-%d") == "2026-12-31"
    assert expected == 365 * 24


def test_calculate_average_weather_success(service: StatisticsService, mock_repo: MagicMock) -> None:
    """Test deterministic calculation with sufficient observations."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Week expected: 168. 70% threshold is ~118 observations.
    # Provide 140 observations
    observations = []
    base_time = datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(140):
        obs = create_observation(
            dt=base_time + timedelta(hours=i),
            temp=20.0 + (i % 10),  # temps between 20 and 29
            feels=22.0 + (i % 10),
            humidity=50.0 + (i % 20),
            wind=10.0 + (i % 5),
            precip=0.5 if i % 2 == 0 else 0.0,
        )
        observations.append(obs)

    mock_repo.get_observations_by_date_range.return_value = observations

    res = service.calculate_average_weather("Indore", "week", reference_date=ref)

    assert res.status == "success"
    assert res.city == "Indore"
    assert res.period == "week"
    assert res.observation_count == 140
    assert res.coverage_percent == round((140 / 168) * 100.0, 1)  # 83.3%
    assert res.minimum_temperature == 20.0
    assert res.maximum_temperature == 29.0
    assert res.average_temperature is not None
    assert res.average_feels_like_temperature is not None
    assert res.average_humidity is not None
    assert res.average_wind_speed is not None
    assert res.total_precipitation == 35.0  # 70 * 0.5


def test_calculate_statistics_with_missing_and_null_values(
    service: StatisticsService, mock_repo: MagicMock
) -> None:
    """Test deterministic calculations correctly ignore null values."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    base_time = datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc)
    observations = []

    # 120 observations (sufficient: 120/168 = 71.4%)
    for i in range(120):
        # Half of the observations have None for optional fields
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

    mock_repo.get_observations_by_date_range.return_value = observations

    res = service.calculate_average_weather("Indore", "week", reference_date=ref)

    assert res.status == "success"
    assert res.average_temperature == 25.0
    assert res.minimum_temperature == 20.0
    assert res.maximum_temperature == 30.0
    # 60 valid feels_like values (all 32.0)
    assert res.average_feels_like_temperature == 32.0
    # 60 valid humidity values (all 80.0)
    assert res.average_humidity == 80.0
    # 60 valid wind values (all 14.0)
    assert res.average_wind_speed == 14.0
    # 60 valid precipitation values (60 * 2.0 = 120.0)
    assert res.total_precipitation == 120.0


def test_calculate_average_weather_insufficient_data(
    service: StatisticsService, mock_repo: MagicMock
) -> None:
    """Test insufficient data response when observation coverage is below 70%."""
    ref = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Only 10 observations out of 168 expected (~6% coverage)
    observations = [
        create_observation(dt=datetime(2026, 9, 28, i, 0, 0, tzinfo=timezone.utc), temp=25.0)
        for i in range(10)
    ]
    mock_repo.get_observations_by_date_range.return_value = observations
    mock_repo.check_available_data_range.return_value = (
        datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 28, 9, 0, 0, tzinfo=timezone.utc),
    )

    res = service.calculate_average_weather("Indore", "week", reference_date=ref)

    assert res.status == "insufficient_data"
    assert res.city == "Indore"
    assert res.period == "week"
    assert res.observation_count == 10
    assert res.coverage_percent == 6.0
    assert res.average_temperature is None
    assert res.minimum_temperature is None
    assert res.maximum_temperature is None
    assert res.available_from == "2026-09-28"
    assert res.available_to == "2026-09-28"
    assert "Not enough historical weather data" in res.message


def test_calculate_average_weather_empty_observations(
    service: StatisticsService, mock_repo: MagicMock
) -> None:
    """Test response when no observations exist at all in the database."""
    mock_repo.get_observations_by_date_range.return_value = []
    mock_repo.check_available_data_range.return_value = (None, None)

    res = service.calculate_average_weather("Indore", "month")

    assert res.status == "insufficient_data"
    assert res.observation_count == 0
    assert res.coverage_percent == 0.0
    assert res.available_from is None
    assert res.available_to is None
