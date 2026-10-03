"""External Weather API client for Google Weather and Geocoding APIs."""

from typing import Any, Dict, Optional
import httpx

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Custom Client Exceptions
class WeatherClientError(Exception):
    """Base exception for all weather client failures."""


class CityNotFoundError(WeatherClientError):
    """Raised when the specified city cannot be found or geocoded."""


class AmbiguousLocationError(WeatherClientError):
    """Raised when a location query matches multiple competing locations without qualification."""


class WeatherAuthenticationError(WeatherClientError):
    """Raised when API key is missing or authentication fails."""


class WeatherRateLimitError(WeatherClientError):
    """Raised when external API rate limit is exceeded."""


class WeatherTimeoutError(WeatherClientError):
    """Raised when an external request times out."""


class WeatherServiceUnavailableError(WeatherClientError):
    """Raised when external service is unreachable or returns a server error."""


class WeatherResponseParsingError(WeatherClientError):
    """Raised when the provider response format is malformed or unexpected."""


class GoogleWeatherClient:
    """Client for Google Geocoding and Google Maps Weather APIs.
    
    Handles low-level HTTP communication, error mappings, and authentication.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        geocoding_base_url: Optional[str] = None,
        weather_base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.google_weather_api_key
        self.timeout = timeout if timeout is not None else settings.weather_api_timeout
        self.geocoding_base_url = (
            geocoding_base_url or settings.google_geocoding_base_url
        )
        self.weather_base_url = (
            weather_base_url or settings.weather_api_base_url
        )

    def geocode_city(self, city: str) -> Dict[str, Any]:
        """Convert a city name into geographical coordinates using Google Geocoding API.
        
        Returns:
            Dict containing latitude, longitude, and formatted_address.
        """
        if not self.api_key:
            logger.error("Weather API key is not configured")
            raise WeatherAuthenticationError("Weather service API key is not configured.")

        params = {
            "address": city,
            "key": self.api_key,
        }

        logger.debug("Geocoding location for city: %s", city)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.geocoding_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Geocoding request timed out for city: %s", city)
            raise WeatherTimeoutError("Geocoding request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error during geocoding: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to connect to location service.") from exc

        if response.status_code in (401, 403):
            logger.error("Geocoding API authentication rejected: status %s", response.status_code)
            raise WeatherAuthenticationError("Location service authentication failed.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Geocoding API JSON response")
            raise WeatherResponseParsingError("Invalid response format from location service.") from exc

        status = payload.get("status")

        if status == "ZERO_RESULTS":
            logger.warning("City '%s' could not be found (ZERO_RESULTS)", city)
            raise CityNotFoundError(f"City '{city}' not found.")

        if status in ("REQUEST_DENIED", "OVER_QUERY_LIMIT"):
            if status == "OVER_QUERY_LIMIT":
                logger.error("Geocoding API quota / rate limit exceeded")
                raise WeatherRateLimitError("Location service quota exceeded. Please try again later.")
            logger.error("Geocoding API request denied: %s", payload.get("error_message", "Unknown reason"))
            raise WeatherAuthenticationError("Location service request was denied. Check API credentials.")

        if status != "OK" or not payload.get("results"):
            logger.warning("Geocoding returned non-OK status: %s", status)
            raise CityNotFoundError(f"City '{city}' could not be resolved.")

        result = payload["results"][0]
        try:
            location = result["geometry"]["location"]
            return {
                "latitude": float(location["lat"]),
                "longitude": float(location["lng"]),
                "formatted_address": result.get("formatted_address", city),
            }
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Malformed geocoding coordinates in response: %s", exc)
            raise WeatherResponseParsingError("Malformed coordinates received from location service.") from exc

    def get_current_conditions(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Fetch real-time current conditions from Google Weather API.
        
        Returns:
            Dict containing raw weather conditions payload.
        """
        if not self.api_key:
            logger.error("Weather API key is not configured")
            raise WeatherAuthenticationError("Weather service API key is not configured.")

        url = f"{self.weather_base_url}/currentConditions:lookup"
        params = {
            "key": self.api_key,
            "location.latitude": latitude,
            "location.longitude": longitude,
            "unitsSystem": "METRIC",
        }

        logger.debug("Requesting current conditions for lat=%s, lng=%s", latitude, longitude)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Google Weather API request timed out")
            raise WeatherTimeoutError("Weather service request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error connecting to Google Weather API: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to reach weather service provider.") from exc

        if response.status_code in (401, 403):
            logger.error("Google Weather API authentication failed (HTTP %s)", response.status_code)
            raise WeatherAuthenticationError("Weather service authentication failed.")

        if response.status_code == 429:
            logger.error("Google Weather API rate limit exceeded")
            raise WeatherRateLimitError("Weather service rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Google Weather API provider error (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("Weather service provider temporarily unavailable.")

        if response.status_code != 200:
            logger.error("Google Weather API returned unexpected status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from weather provider.")

        try:
            return response.json()
        except Exception as exc:
            logger.error("Failed to parse Google Weather API JSON response: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON received from weather service.") from exc

    def get_forecast(self, latitude: float, longitude: float, days: int = 5) -> Dict[str, Any]:
        """Fetch multi-day weather forecast from Google Weather API.
        
        Args:
            latitude: Geographic latitude
            longitude: Geographic longitude
            days: Number of forecast days (1-10)
            
        Returns:
            Dict containing raw forecast days payload.
        """
        if not self.api_key:
            logger.error("Weather API key is not configured")
            raise WeatherAuthenticationError("Weather service API key is not configured.")

        url = f"{self.weather_base_url}/forecast/days:lookup"
        params = {
            "key": self.api_key,
            "location.latitude": latitude,
            "location.longitude": longitude,
            "days": days,
            "unitsSystem": "METRIC",
        }

        logger.debug("Requesting forecast for lat=%s, lng=%s, days=%s", latitude, longitude, days)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Google Weather forecast request timed out")
            raise WeatherTimeoutError("Weather forecast request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error connecting to Google Weather forecast API: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to reach weather service provider.") from exc

        if response.status_code in (401, 403):
            logger.error("Google Weather API authentication failed (HTTP %s)", response.status_code)
            raise WeatherAuthenticationError("Weather service authentication failed.")

        if response.status_code == 429:
            logger.error("Google Weather API rate limit exceeded")
            raise WeatherRateLimitError("Weather service rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Google Weather API provider error (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("Weather service provider temporarily unavailable.")

        if response.status_code != 200:
            logger.error("Google Weather API returned unexpected status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from weather provider.")

        try:
            return response.json()
        except Exception as exc:
            logger.error("Failed to parse Google Weather forecast JSON response: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON received from weather service.") from exc

    def get_historical_hours(self, latitude: float, longitude: float, hours: int = 24) -> Dict[str, Any]:
        """Fetch hourly historical weather data from Google Weather API.
        
        Args:
            latitude: Geographic latitude
            longitude: Geographic longitude
            hours: Number of historical hours to retrieve (1-24)
            
        Returns:
            Dict containing raw historical hours payload (historyHours).
        """
        if not self.api_key:
            logger.error("Weather API key is not configured")
            raise WeatherAuthenticationError("Weather service API key is not configured.")

        # Google Maps Weather historical endpoint supports up to 24 hours
        safe_hours = max(1, min(int(hours), 24))

        url = f"{self.weather_base_url}/history/hours:lookup"
        params = {
            "key": self.api_key,
            "location.latitude": latitude,
            "location.longitude": longitude,
            "hours": safe_hours,
            "unitsSystem": "METRIC",
        }

        logger.debug("Requesting historical hours for lat=%s, lng=%s, hours=%s", latitude, longitude, safe_hours)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Google Weather historical request timed out")
            raise WeatherTimeoutError("Weather historical request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error connecting to Google Weather historical API: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to reach weather service provider.") from exc

        if response.status_code in (401, 403):
            logger.error("Google Weather API authentication failed (HTTP %s)", response.status_code)
            raise WeatherAuthenticationError("Weather service authentication failed.")

        if response.status_code == 429:
            logger.error("Google Weather API rate limit exceeded")
            raise WeatherRateLimitError("Weather service rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Google Weather API provider error (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("Weather service provider temporarily unavailable.")

        if response.status_code != 200:
            logger.error("Google Weather API returned unexpected status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from weather provider.")

        try:
            return response.json()
        except Exception as exc:
            logger.error("Failed to parse Google Weather historical JSON response: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON received from weather service.") from exc

