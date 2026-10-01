"""Health check business service."""

from app.config.settings import Settings, get_settings
from app.schemas.health import HealthResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HealthService:
    """Service responsible for assessing system health status."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_health_status(self) -> HealthResponse:
        """Produce the current health status of the application."""
        logger.debug("Generating system health status report")
        return HealthResponse(status="ok")
