"""Repository abstraction for weather observations persistence and querying."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.weather_observation import WeatherObservation
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherObservationRepository:
    """Encapsulates database operations for weather observations.
    
    Architecture Rules:
    - Service -> Repository -> Model/Database.
    - Router and Statistics Service must never write SQL directly.
    - City comparisons are case-normalized.
    - Timestamps are handled in UTC.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _normalize_city(city: str) -> str:
        """Strip and normalize city string."""
        return city.strip().title()

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Ensure a datetime object is timezone-aware in UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def save_observation(
        self,
        observation: Union[WeatherObservation, Dict],
    ) -> WeatherObservation:
        """Save a weather observation with deduplication.
        
        If an observation already exists for the same city and observation timestamp,
        the existing record is returned without creating duplicates.
        """
        if isinstance(observation, dict):
            city_norm = self._normalize_city(observation["city"])
            observed_dt = self._ensure_utc(observation["observed_at"])
            
            # Check for existing observation
            existing = (
                self.db.query(WeatherObservation)
                .filter(
                    func.lower(WeatherObservation.city) == city_norm.lower(),
                    WeatherObservation.observed_at == observed_dt,
                )
                .first()
            )
            if existing:
                logger.debug("Deduplication matched existing observation for %s at %s", city_norm, observed_dt)
                return existing

            record = WeatherObservation(
                city=city_norm,
                latitude=observation["latitude"],
                longitude=observation["longitude"],
                observed_at=observed_dt,
                temperature=observation["temperature"],
                feels_like_temperature=observation.get("feels_like_temperature"),
                humidity=observation.get("humidity"),
                precipitation=observation.get("precipitation", 0.0) or 0.0,
                wind_speed=observation.get("wind_speed"),
                pressure=observation.get("pressure"),
                weather_condition=observation.get("weather_condition"),
                source=observation.get("source", "google"),
            )
        else:
            record = observation
            record.city = self._normalize_city(record.city)
            record.observed_at = self._ensure_utc(record.observed_at)

            existing = (
                self.db.query(WeatherObservation)
                .filter(
                    func.lower(WeatherObservation.city) == record.city.lower(),
                    WeatherObservation.observed_at == record.observed_at,
                )
                .first()
            )
            if existing:
                logger.debug("Deduplication matched existing record for %s at %s", record.city, record.observed_at)
                return existing

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            logger.info("Persisted new weather observation id=%s for city='%s'", record.id, record.city)
            return record
        except IntegrityError:
            self.db.rollback()
            # Race condition deduplication fallback
            existing = (
                self.db.query(WeatherObservation)
                .filter(
                    func.lower(WeatherObservation.city) == record.city.lower(),
                    WeatherObservation.observed_at == record.observed_at,
                )
                .first()
            )
            if existing:
                return existing
            raise

    def get_observations_by_city(
        self,
        city: str,
        limit: int = 100,
    ) -> List[WeatherObservation]:
        """Retrieve recent observations for a city."""
        city_norm = self._normalize_city(city)
        return (
            self.db.query(WeatherObservation)
            .filter(func.lower(WeatherObservation.city) == city_norm.lower())
            .order_by(WeatherObservation.observed_at.desc())
            .limit(limit)
            .all()
        )

    def get_observations_by_date_range(
        self,
        city: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[WeatherObservation]:
        """Retrieve observations for a city within a specified UTC datetime range.
        
        Ordered chronologically ascending.
        """
        city_norm = self._normalize_city(city)
        start_utc = self._ensure_utc(start_date)
        end_utc = self._ensure_utc(end_date)

        return (
            self.db.query(WeatherObservation)
            .filter(
                func.lower(WeatherObservation.city) == city_norm.lower(),
                WeatherObservation.observed_at >= start_utc,
                WeatherObservation.observed_at <= end_utc,
            )
            .order_by(WeatherObservation.observed_at.asc())
            .all()
        )

    def count_observations(
        self,
        city: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count total observations for a city, optionally bounded by date range."""
        city_norm = self._normalize_city(city)
        query = self.db.query(func.count(WeatherObservation.id)).filter(
            func.lower(WeatherObservation.city) == city_norm.lower()
        )
        if start_date is not None:
            query = query.filter(WeatherObservation.observed_at >= self._ensure_utc(start_date))
        if end_date is not None:
            query = query.filter(WeatherObservation.observed_at <= self._ensure_utc(end_date))
        return query.scalar() or 0

    def check_available_data_range(
        self,
        city: str,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Return the earliest and latest observation timestamps available for a city."""
        city_norm = self._normalize_city(city)
        result = (
            self.db.query(
                func.min(WeatherObservation.observed_at),
                func.max(WeatherObservation.observed_at),
            )
            .filter(func.lower(WeatherObservation.city) == city_norm.lower())
            .first()
        )
        if result and result[0] is not None and result[1] is not None:
            return result[0], result[1]
        return None, None
