"""Repositories layer: Data access and persistence abstractions.

Architecture Rule:
- Encapsulates database queries.
- Service -> Repository -> Model/Database.
"""

from app.repositories.weather_observation_repository import WeatherObservationRepository

__all__ = ["WeatherObservationRepository"]
