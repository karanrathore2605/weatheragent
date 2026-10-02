"""Unit and integration tests for WeatherObservationRepository using in-memory SQLite."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models.weather_observation import WeatherObservation
from app.repositories.weather_observation_repository import WeatherObservationRepository


@pytest.fixture
def db_session():
    """Fixture providing an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def repository(db_session):
    """Fixture providing repository instance with in-memory DB."""
    return WeatherObservationRepository(db_session)


def test_save_observation_dict(repository: WeatherObservationRepository) -> None:
    """Test saving an observation dictionary."""
    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    data = {
        "city": "Indore",
        "latitude": 22.7196,
        "longitude": 75.8577,
        "observed_at": now,
        "temperature": 28.5,
        "feels_like_temperature": 30.0,
        "humidity": 65.0,
        "precipitation": 1.2,
        "wind_speed": 12.0,
        "pressure": 1012.0,
        "weather_condition": "Partly Cloudy",
        "source": "google",
    }

    obs = repository.save_observation(data)
    assert obs.id is not None
    assert obs.city == "Indore"
    assert obs.temperature == 28.5
    assert obs.precipitation == 1.2


def test_save_observation_deduplication(repository: WeatherObservationRepository) -> None:
    """Test deduplication: saving identical city and observation timestamp returns existing row."""
    now = datetime(2026, 10, 1, 14, 0, 0, tzinfo=timezone.utc)
    data1 = {
        "city": "Indore",
        "latitude": 22.7196,
        "longitude": 75.8577,
        "observed_at": now,
        "temperature": 28.5,
    }
    data2 = {
        "city": "indore",  # different casing
        "latitude": 22.7196,
        "longitude": 75.8577,
        "observed_at": now,
        "temperature": 29.0,  # duplicate attempt
    }

    obs1 = repository.save_observation(data1)
    obs2 = repository.save_observation(data2)

    assert obs1.id == obs2.id
    assert repository.count_observations("Indore") == 1


def test_get_observations_by_city(repository: WeatherObservationRepository) -> None:
    """Test retrieving observations by city with ordering and limit."""
    base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        repository.save_observation({
            "city": "Indore",
            "latitude": 22.7,
            "longitude": 75.8,
            "observed_at": base_time + timedelta(hours=i),
            "temperature": 25.0 + i,
        })
    # Another city
    repository.save_observation({
        "city": "Bhopal",
        "latitude": 23.2,
        "longitude": 77.4,
        "observed_at": base_time,
        "temperature": 26.0,
    })

    indore_records = repository.get_observations_by_city("indore", limit=3)
    assert len(indore_records) == 3
    # Ordered descending by observed_at
    assert indore_records[0].temperature == 29.0


def test_get_observations_by_date_range(repository: WeatherObservationRepository) -> None:
    """Test querying observations by date range bounds."""
    base = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        repository.save_observation({
            "city": "Indore",
            "latitude": 22.7,
            "longitude": 75.8,
            "observed_at": base + timedelta(hours=i),
            "temperature": 20.0 + i,
        })

    # Range: hours 2 to 5 inclusive
    start = base + timedelta(hours=2)
    end = base + timedelta(hours=5)
    results = repository.get_observations_by_date_range("Indore", start, end)

    assert len(results) == 4
    assert [r.temperature for r in results] == [22.0, 23.0, 24.0, 25.0]


def test_count_observations(repository: WeatherObservationRepository) -> None:
    """Test counting observations with and without date range."""
    base = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(6):
        repository.save_observation({
            "city": "Indore",
            "latitude": 22.7,
            "longitude": 75.8,
            "observed_at": base + timedelta(hours=i),
            "temperature": 20.0 + i,
        })

    assert repository.count_observations("Indore") == 6
    assert repository.count_observations("Indore", start_date=base + timedelta(hours=2)) == 4
    assert repository.count_observations("NonExistentCity") == 0


def test_check_available_data_range(repository: WeatherObservationRepository) -> None:
    """Test checking earliest and latest observation dates."""
    earliest = datetime(2026, 9, 25, 8, 0, 0, tzinfo=timezone.utc)
    latest = datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc)

    repository.save_observation({
        "city": "Indore",
        "latitude": 22.7,
        "longitude": 75.8,
        "observed_at": earliest,
        "temperature": 22.0,
    })
    repository.save_observation({
        "city": "Indore",
        "latitude": 22.7,
        "longitude": 75.8,
        "observed_at": latest,
        "temperature": 28.0,
    })

    min_dt, max_dt = repository.check_available_data_range("indore")
    assert min_dt is not None
    assert max_dt is not None
    assert min_dt.replace(tzinfo=timezone.utc) == earliest
    assert max_dt.replace(tzinfo=timezone.utc) == latest

    # Non-existent city returns None, None
    no_min, no_max = repository.check_available_data_range("Nowhere")
    assert no_min is None
    assert no_max is None
