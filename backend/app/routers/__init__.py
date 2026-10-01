"""Routers layer: HTTP endpoint definitions and API routing.

Architecture Rule:
- Routers handle HTTP request parsing, status codes, and response serialization.
- Routers delegate all domain logic to Services (Router -> Service).
"""

from app.routers.health import router as health_router

__all__ = ["health_router"]
