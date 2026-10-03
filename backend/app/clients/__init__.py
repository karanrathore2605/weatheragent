"""Clients layer: Third-party API and external service communication wrappers.

Architecture Rule:
- Service -> Client -> External API.
- Clients encapsulate low-level protocol and authentication details.
"""

from app.clients.accuweather_client import AccuWeatherClient
from app.clients.groq_client import (
    BaseLLMClient,
    GroqClient,
    LLMAuthenticationError,
    LLMClientError,
    LLMEmptyResponseError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from app.clients.open_meteo_client import OpenMeteoClient
from app.clients.weather_client import (
    GoogleWeatherClient,
    WeatherClientError,
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherTimeoutError,
    WeatherServiceUnavailableError,
    WeatherResponseParsingError,
)

__all__ = [
    "AccuWeatherClient",
    "BaseLLMClient",
    "GoogleWeatherClient",
    "GroqClient",
    "LLMAuthenticationError",
    "LLMClientError",
    "LLMEmptyResponseError",
    "LLMRateLimitError",
    "LLMServiceUnavailableError",
    "LLMTimeoutError",
    "OpenMeteoClient",
    "WeatherClientError",
    "CityNotFoundError",
    "WeatherAuthenticationError",
    "WeatherRateLimitError",
    "WeatherTimeoutError",
    "WeatherServiceUnavailableError",
    "WeatherResponseParsingError",
]
