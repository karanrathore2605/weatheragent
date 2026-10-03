"""Router for Monthly Weather Report generation."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.clients.weather_client import (
    AmbiguousLocationError,
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.schemas.monthly_report_schema import (
    MonthlyWeatherReportRequest,
    MonthlyWeatherReportResponse,
)
from app.schemas.weather_schema import WeatherErrorResponse
from app.services.monthly_report_service import MonthlyReportService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/weather/report", tags=["Monthly Weather Report"])


def get_monthly_report_service() -> MonthlyReportService:
    """Dependency provider for MonthlyReportService."""
    return MonthlyReportService()


@router.get(
    "/monthly",
    response_model=MonthlyWeatherReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Monthly Weather Report",
    description="Fetch historical weather data for a selected month, calculate weekly averages, and generate a professional AI summary.",
    responses={
        200: {
            "model": MonthlyWeatherReportResponse,
            "description": "Monthly weather report generated successfully",
        },
        400: {"model": WeatherErrorResponse, "description": "Invalid city or month parameter"},
        404: {"model": WeatherErrorResponse, "description": "City not found"},
        429: {"model": WeatherErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": WeatherErrorResponse, "description": "Internal server error"},
        502: {"model": WeatherErrorResponse, "description": "Bad gateway from upstream provider"},
        503: {"model": WeatherErrorResponse, "description": "Historical weather service provider unavailable"},
        504: {"model": WeatherErrorResponse, "description": "Historical weather service provider timed out"},
    },
)
def get_monthly_weather_report(
    city: str = Query(..., description="Target city name (e.g. Indore, Bhopal, Mumbai)", examples=["Indore"]),
    month: Optional[str] = Query(default=None, description="Target month string (e.g. 'August 2026', '2026-08', 'August')", examples=["August 2026"]),
    year: Optional[int] = Query(default=None, description="Target year integer (e.g. 2026)", examples=[2026]),
    month_num: Optional[int] = Query(default=None, description="Target month number (1-12)", examples=[8]),
    service: MonthlyReportService = Depends(get_monthly_report_service),
) -> MonthlyWeatherReportResponse:
    """Handle GET /api/v1/weather/report/monthly request."""
    logger.info("Received GET Monthly Weather Report request: city='%s', month='%s', year=%s", city, month, year)

    if not city or not city.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="City name cannot be empty.",
        )

    effective_month = month if month is not None else month_num

    try:
        return service.generate_report(
            city=city.strip(),
            month_input=effective_month,
            year_input=year,
        )
    except CityNotFoundError as exc:
        logger.warning("City not found: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AmbiguousLocationError as exc:
        logger.warning("Ambiguous city: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Validation error on monthly report request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except WeatherTimeoutError as exc:
        logger.error("Historical weather service timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Historical weather service timed out. Please try again.",
        ) from exc
    except WeatherRateLimitError as exc:
        logger.error("Historical weather service rate limit exceeded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Historical weather service rate limit exceeded. Please try again later.",
        ) from exc
    except WeatherServiceUnavailableError as exc:
        logger.error("Historical weather service unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Historical weather service is currently unavailable. Please try again.",
        ) from exc
    except WeatherResponseParsingError as exc:
        logger.error("Failed to parse historical weather response: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from historical weather service provider.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error generating monthly weather report: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the weather report.",
        ) from exc


@router.post(
    "/monthly",
    response_model=MonthlyWeatherReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Monthly Weather Report (POST)",
    description="Generate monthly weather report using JSON request body.",
    responses={
        200: {"model": MonthlyWeatherReportResponse, "description": "Monthly weather report generated successfully"},
        400: {"model": WeatherErrorResponse, "description": "Invalid input parameters"},
        404: {"model": WeatherErrorResponse, "description": "City not found"},
    },
)
def post_monthly_weather_report(
    payload: MonthlyWeatherReportRequest,
    service: MonthlyReportService = Depends(get_monthly_report_service),
) -> MonthlyWeatherReportResponse:
    """Handle POST /api/v1/weather/report/monthly request."""
    return get_monthly_weather_report(
        city=payload.city,
        month=payload.month,
        year=payload.year,
        month_num=payload.month_num,
        service=service,
    )
