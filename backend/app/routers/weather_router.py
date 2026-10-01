"""Weather endpoints routing and HTTP request/response handling."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.schemas.weather_schema import WeatherErrorResponse, WeatherResponse
from app.services.weather_service import WeatherService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather"])


def get_weather_service() -> WeatherService:
    """Dependency provider for WeatherService."""
    return WeatherService()


@router.get(
    "/current",
    response_model=WeatherResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Weather",
    description="Retrieve live current weather metrics for a specified city.",
    responses={
        200: {"model": WeatherResponse, "description": "Current weather retrieved successfully"},
        400: {"model": WeatherErrorResponse, "description": "Invalid or empty city parameter"},
        404: {"model": WeatherErrorResponse, "description": "City not found"},
        429: {"model": WeatherErrorResponse, "description": "Weather provider rate limit exceeded"},
        502: {"model": WeatherErrorResponse, "description": "Bad gateway or malformed provider response"},
        503: {"model": WeatherErrorResponse, "description": "Weather service unavailable or authentication failed"},
        504: {"model": WeatherErrorResponse, "description": "Weather provider request timed out"},
    },
)
def get_current_weather_endpoint(
    city: str = Query(
        ...,
        description="Name of the city (e.g. Indore, Delhi, London)",
        examples=["Indore"],
    ),
    service: WeatherService = Depends(get_weather_service),
) -> WeatherResponse:
    """Handle GET /current weather request."""
    logger.info("Received request for current weather: city='%s'", city)

    try:
        return service.get_current_weather(city)
    except ValueError as exc:
        logger.warning("Validation error for city '%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CityNotFoundError as exc:
        logger.warning("City not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WeatherAuthenticationError as exc:
        logger.error("Authentication error accessing weather API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather service authentication failed or API key is not configured.",
        ) from exc
    except WeatherRateLimitError as exc:
        logger.error("Rate limit hit from weather provider: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Weather provider rate limit exceeded. Please try again later.",
        ) from exc
    except WeatherTimeoutError as exc:
        logger.error("Timeout occurred while contacting weather provider: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Weather provider request timed out.",
        ) from exc
    except WeatherServiceUnavailableError as exc:
        logger.error("Weather service provider unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather service is currently unavailable.",
        ) from exc
    except WeatherResponseParsingError as exc:
        logger.error("Malformed weather response received: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Received an invalid response from weather provider.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error processing weather for city '%s': %s", city, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching weather data.",
        ) from exc
