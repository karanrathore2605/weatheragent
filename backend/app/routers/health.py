"""Health check router endpoints."""

from fastapi import APIRouter, Depends, status

from app.schemas.health import HealthResponse
from app.services.health_service import HealthService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


def get_health_service() -> HealthService:
    """Dependency provider for HealthService."""
    return HealthService()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns current application health status, environment, and version.",
)
def check_health(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """Handle GET /health check request."""
    logger.info("Health check endpoint accessed")
    return service.get_health_status()
