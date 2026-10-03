"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.database.session import init_db
from app.routers.agent_router import router as agent_router
from app.routers.health import router as health_router
from app.routers.monthly_report_router import router as monthly_report_router
from app.routers.statistics_router import router as statistics_router
from app.routers.weather_router import router as weather_router
from app.utils.logger import get_logger, setup_logging

logger = get_logger("weather_agent.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown lifecycle events."""
    setup_logging()
    logger.info(
        "Starting %s [version: %s, env: %s]",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    logger.info("Allowed CORS origins: %s", settings.cors_origins)
    # Initialize database tables
    try:
        init_db()
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_application() -> FastAPI:
    """Application factory for FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health_router)
    app.include_router(weather_router, prefix="/api/v1")
    app.include_router(statistics_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(monthly_report_router, prefix="/api/v1")

    @app.get("/", tags=["Root"])
    def root():
        """Root endpoint."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "docs": "/docs",
            "health": "/health",
            "weather": "/api/v1/weather/current",
            "forecast": "/api/v1/weather/forecast",
            "statistics": "/api/v1/weather/statistics",
            "summary": "/api/v1/weather/statistics/summary",
            "agent": "/api/v1/agent/query",
            "monthly_report": "/api/v1/weather/report/monthly",
        }

    return app


app = create_application()
