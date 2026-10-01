"""Schemas layer: Contains Pydantic models for request/response validation.

Architecture Rule:
- Schemas define the contract between client and API (DTOs).
- Schemas are kept strictly separated from database models.
"""

from app.schemas.health import HealthResponse

__all__ = ["HealthResponse"]
