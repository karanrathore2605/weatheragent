"""Weather statistics routing and HTTP request/response validation."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import (
    StatisticsPeriod,
    WeatherErrorResponse,
    WeatherStatisticsResponse,
    WeatherSummaryResponse,
)

from app.services.statistics_service import StatisticsService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather Statistics"])


def get_statistics_service(db: Session = Depends(get_db)) -> StatisticsService:
    """Dependency provider injecting repository into StatisticsService."""
    repository = WeatherObservationRepository(db)
    return StatisticsService(repository=repository)


@router.get(
    "/statistics",
    response_model=WeatherStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Weather Statistics",
    description="Compute deterministic historical weather statistics for a city over a week, month, or year.",
    responses={
        200: {
            "model": WeatherStatisticsResponse,
            "description": "Weather statistics or insufficient data report retrieved successfully",
        },
        400: {"model": WeatherErrorResponse, "description": "Invalid city or unsupported statistics period"},
        500: {"model": WeatherErrorResponse, "description": "Internal database or computation error"},
    },
)
def get_weather_statistics_endpoint(
    city: str = Query(
        ...,
        description="Name of the city (e.g. Indore, Delhi, London)",
        examples=["Indore"],
    ),
    period: StatisticsPeriod = Query(
        default=StatisticsPeriod.WEEK,
        description="Aggregation time horizon ('week', 'month', 'year')",
        examples=[StatisticsPeriod.WEEK],
    ),
    service: StatisticsService = Depends(get_statistics_service),
) -> WeatherStatisticsResponse:
    """Handle GET /api/v1/weather/statistics request."""
    logger.info("Received statistics request: city='%s', period='%s'", city, period.value)

    try:
        return service.calculate_average_weather(city=city, period=period)
    except ValueError as exc:
        logger.warning("Validation error on statistics request for city='%s', period='%s': %s", city, period, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error calculating statistics for city='%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while calculating weather statistics.",
        ) from exc


@router.get(
    "/statistics/summary",
    response_model=WeatherSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Weather Statistics and AI Summary",
    description="Compute deterministic historical weather statistics and generate an AI natural-language summary using Groq.",
    responses={
        200: {
            "model": WeatherSummaryResponse,
            "description": "Weather statistics with natural language summary retrieved successfully",
        },
        400: {"model": WeatherErrorResponse, "description": "Invalid city or unsupported statistics period"},
        500: {"model": WeatherErrorResponse, "description": "Internal database or processing error"},
    },
)
def get_weather_statistics_summary_endpoint(
    city: str = Query(
        ...,
        description="Name of the city (e.g. Indore, Delhi, London)",
        examples=["Indore"],
    ),
    period: StatisticsPeriod = Query(
        default=StatisticsPeriod.WEEK,
        description="Aggregation time horizon ('week', 'month', 'year')",
        examples=[StatisticsPeriod.WEEK],
    ),
    service: StatisticsService = Depends(get_statistics_service),
) -> WeatherSummaryResponse:
    """Handle GET /api/v1/weather/statistics/summary request."""
    logger.info("Received statistics summary request: city='%s', period='%s'", city, period.value)

    try:
        return service.get_weather_summary(city=city, period=period)
    except ValueError as exc:
        logger.warning(
            "Validation error on statistics summary request for city='%s', period='%s': %s",
            city,
            period,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error generating statistics summary for city='%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating weather summary.",
        ) from exc

