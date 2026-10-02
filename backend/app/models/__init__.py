"""Models layer: Database entity definitions (e.g. SQLAlchemy / ORM).

Architecture Rule:
- Database models define persistence structures.
- Schemas are separate from database models.
"""

from app.models.weather_observation import WeatherObservation

__all__ = ["WeatherObservation"]
