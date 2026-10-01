"""Services layer: Contains core business logic and domain processing.

Architecture Rule:
- Routers call Services.
- Tools call Services.
- Services coordinate between Clients (external APIs) and Repositories (database).
"""

from app.services.health_service import HealthService

__all__ = ["HealthService"]
