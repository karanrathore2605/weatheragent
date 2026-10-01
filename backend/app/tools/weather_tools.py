"""Thin weather tool interfaces prepared for future LangGraph integration."""

from typing import Optional
from app.schemas.weather_schema import ForecastResponse, WeatherResponse
from app.services.weather_service import WeatherService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_current_weather(city: str, service: Optional[WeatherService] = None) -> WeatherResponse:
    """Fetch the current weather for a requested city.
    
    Architecture Rule:
    - Agent -> Tool -> Service -> Client.
    - Thin tool layer designed for future LangGraph state graph tool-binding.
    - Does not contain business logic; delegates directly to WeatherService.
    
    Args:
        city: Name of the city to look up (e.g. 'Indore', 'Bhopal').
        service: Optional injected WeatherService instance (defaults to new instance).
        
    Returns:
        Canonical WeatherResponse model containing temperature, conditions, humidity, etc.
    """
    logger.info("Tool invoked: get_current_weather for city '%s'", city)
    active_service = service or WeatherService()
    return active_service.get_current_weather(city)


def get_weather_forecast(
    city: str,
    days: int = 5,
    service: Optional[WeatherService] = None,
) -> ForecastResponse:
    """Fetch multi-day weather forecast for a requested city.
    
    Architecture Rule:
    - Agent -> Tool -> Service -> Client.
    - Thin tool layer designed for future LangGraph state graph tool-binding.
    - Does not contain business logic; delegates directly to WeatherService.
    
    Args:
        city: Name of the city to look up.
        days: Number of forecast days (1-10).
        service: Optional injected WeatherService instance.
        
    Returns:
        Canonical ForecastResponse model containing list of daily metrics.
    """
    logger.info("Tool invoked: get_weather_forecast for city '%s' (days=%s)", city, days)
    active_service = service or WeatherService()
    return active_service.get_forecast(city=city, days=days)
