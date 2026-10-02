"""Weather statistics routing and HTTP request/response validation using Open-Meteo."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.database.session import get_db
from app.schemas.weather_schema import (
    WeatherErrorResponse,
    WeatherStatisticsResponse,
)
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.statistics_service import StatisticsService
from app.services.weather.open_meteo_client import OpenMeteoClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather Statistics"])


def get_statistics_service(db: Session = Depends(get_db)) -> StatisticsService:
    """Dependency provider injecting OpenMeteoClient and HistoricalWeatherService."""
    open_meteo_client = OpenMeteoClient()
    historical_service = HistoricalWeatherService(
        open_meteo_client=open_meteo_client,
    )
    return StatisticsService(
        historical_service=historical_service,
        open_meteo_client=open_meteo_client,
    )


@router.get(
    "/statistics",
    response_model=WeatherStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Historical Weather Statistics",
    description="Compute average temperature for a city over 1-4 weeks or 1-12 months via Open-Meteo Historical Weather API.",
    responses={
        200: {
            "model": WeatherStatisticsResponse,
            "description": "Historical weather statistics retrieved successfully",
        },
        400: {"model": WeatherErrorResponse, "description": "Invalid city or unsupported statistics period/duration"},
        404: {"model": WeatherErrorResponse, "description": "City not found"},
        429: {"model": WeatherErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": WeatherErrorResponse, "description": "Internal server or computation error"},
        503: {"model": WeatherErrorResponse, "description": "Historical weather service provider unavailable"},
        504: {"model": WeatherErrorResponse, "description": "Historical weather service provider timed out"},
    },
)
def get_weather_statistics_endpoint(
    city: str = Query(
        ...,
        description="Name of the city (e.g. Indore, Delhi, Mumbai, Pune)",
        examples=["Indore"],
    ),
    period_type: Optional[str] = Query(
        default=None,
        description="Aggregation time horizon ('week', 'month')",
        examples=["week"],
    ),
    period: Optional[str] = Query(
        default=None,
        description="Legacy alias for period_type ('week', 'month')",
        examples=["week"],
    ),
    duration: Optional[int] = Query(
        default=None,
        description="Duration integer (1-4 for week; 1-12 for month)",
        examples=[1],
    ),
    period_value: Optional[int] = Query(
        default=None,
        description="Alias for duration integer",
        examples=[1],
    ),
    service: StatisticsService = Depends(get_statistics_service),
) -> WeatherStatisticsResponse:
    """Handle GET /api/v1/weather/statistics request."""
    effective_period = (period_type if period_type is not None else (period or "week")).strip().lower()
    effective_duration = duration if duration is not None else (period_value if period_value is not None else 1)

    logger.info(
        "Received historical statistics request: city='%s', period='%s', duration=%s",
        city,
        effective_period,
        effective_duration,
    )

    # HTTP Parameter validation
    if not city or not city.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="City name cannot be empty.",
        )

    if effective_period == "year":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The 'year' period option has been removed. Supported periods: week, month.",
        )

    if effective_period not in ("week", "month"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid statistics period '{effective_period}'. Supported periods: week, month.",
        )

    if effective_period == "week" and effective_duration not in (1, 2, 3, 4):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid week duration: {effective_duration}. Supported durations for week: 1, 2, 3, or 4 weeks.",
        )

    if effective_period == "month" and effective_duration not in tuple(range(1, 13)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid month duration: {effective_duration}. Supported durations for month: 1 to 12 months.",
        )

    try:
        return service.calculate_average_weather(
            city=city,
            period=effective_period,
            period_value=effective_duration,
            duration=effective_duration,
        )
    except CityNotFoundError as exc:
        logger.warning("City not found for statistics request '%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        logger.warning("Validation error on statistics request for city='%s', period='%s': %s", city, effective_period, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WeatherTimeoutError as exc:
        logger.error("Historical weather service timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Unable to retrieve historical weather data right now. Please try again.",
        ) from exc
    except WeatherRateLimitError as exc:
        logger.error("Historical weather rate limit exceeded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Historical weather service rate limit exceeded. Please try again later.",
        ) from exc
    except WeatherServiceUnavailableError as exc:
        logger.error("Historical weather service unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to retrieve historical weather data right now. Please try again.",
        ) from exc
    except WeatherResponseParsingError as exc:
        logger.error("Historical weather response parsing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve historical weather data right now. Please try again.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error calculating statistics for city='%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve historical weather data right now. Please try again.",
        ) from exc
