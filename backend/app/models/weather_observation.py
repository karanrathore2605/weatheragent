"""Weather observation database model."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint

from app.database.session import Base


class WeatherObservation(Base):
    """Persistent weather observation recorded from weather providers.
    
    Architecture Rules:
    - Stores raw deterministic observations.
    - City and observation timestamp form a deduplication constraint.
    - Indexed by city and observed_at for efficient time-series aggregation.
    - Internal timestamps are UTC timezone-aware.
    """

    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    city = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    temperature = Column(Float, nullable=False)
    feels_like_temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    precipitation = Column(Float, nullable=True, default=0.0)
    wind_speed = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    weather_condition = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False, default="google")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_weather_obs_city_observed_at", "city", "observed_at"),
        UniqueConstraint("city", "observed_at", name="uq_city_observed_at"),
    )

    def __repr__(self) -> str:
        return f"<WeatherObservation(city='{self.city}', observed_at='{self.observed_at}', temp={self.temperature})>"
