"""Services layer: Contains core business logic and domain processing.

Architecture Rule:
- Routers call Services.
- Tools call Services.
- Services coordinate between Clients (external APIs) and Repositories (database).
"""

from app.services.health_service import HealthService
from app.services.statistics_service import StatisticsService
from app.services.weather_service import WeatherService

__all__ = ["HealthService", "StatisticsService", "WeatherService"]
