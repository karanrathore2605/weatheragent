"""Data schemas for health check and system status responses."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Pydantic schema representing the system health check response."""

    status: str = Field(default="ok", description="Current service health status")
