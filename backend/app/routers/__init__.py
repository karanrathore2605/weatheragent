"""Routers layer: HTTP endpoint definitions and API routing.

Architecture Rule:
- Routers handle HTTP request parsing, status codes, and response serialization.
- Routers delegate all domain logic to Services (Router -> Service).
"""

from app.routers.health import router as health_router
from app.routers.statistics_router import router as statistics_router
from app.routers.weather_router import router as weather_router

__all__ = ["health_router", "statistics_router", "weather_router"]
