"""AccuWeather external API client.

Architecture Rules:
- Direct HTTP communication with AccuWeather Locations and Current Conditions APIs.
- Resolves city names to AccuWeather location keys and caches results.
- Retrieves past hourly historical conditions (up to 24 hours via Core Weather API).
- Strict error mapping (auth, rate limits, timeouts, service unavailable, not found).
- Never leaks API keys or internal stack traces.
"""

from typing import Any, Dict, List, Optional
import httpx

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherClientError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AccuWeatherClient:
    """Client for official AccuWeather Locations and Weather APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.accuweather_api_key
        self.timeout = timeout if timeout is not None else settings.weather_api_timeout
        self.base_url = (base_url or settings.accuweather_base_url).rstrip("/")
        # In-memory location key cache: city_lower -> location dict
        self._location_cache: Dict[str, Dict[str, Any]] = {}

    def search_location(self, city: str) -> Dict[str, Any]:
        """Resolve a city name to an AccuWeather location key.
        
        Args:
            city: City name string (e.g. 'Indore', 'London')
            
        Returns:
            Dict containing location key, localized name, and coordinates.
            
        Raises:
            WeatherAuthenticationError: If API key is missing or invalid.
            CityNotFoundError: If the city cannot be resolved.
            WeatherTimeoutError: If the request times out.
            WeatherRateLimitError: If API quota is exceeded.
            WeatherServiceUnavailableError: If AccuWeather service is unreachable.
        """
        if not city or not city.strip():
            raise CityNotFoundError("City name cannot be empty.")

        city_clean = city.strip()
        cache_key = city_clean.lower()

        # Check location key cache
        if cache_key in self._location_cache:
            logger.debug("AccuWeather location key cache hit for '%s'", city_clean)
            return self._location_cache[cache_key]

        if not self.api_key:
            logger.error("AccuWeather API key is not configured")
            raise WeatherAuthenticationError("AccuWeather API key is not configured.")

        url = f"{self.base_url}/locations/v1/cities/search"
        params = {
            "apikey": self.api_key,
            "q": city_clean,
            "language": "en-us",
        }

        logger.debug("Searching AccuWeather location key for city: %s", city_clean)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("AccuWeather location search timed out for city: %s", city_clean)
            raise WeatherTimeoutError("AccuWeather location search request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error during AccuWeather location search: %s", exc)
            raise WeatherServiceUnavailableError("Unable to reach AccuWeather location service.") from exc

        if response.status_code in (401, 403):
            logger.error("AccuWeather authentication failed on location search (HTTP %s)", response.status_code)
            raise WeatherAuthenticationError("AccuWeather service authentication failed.")

        if response.status_code == 404:
            logger.warning("AccuWeather returned 404 for city: %s", city_clean)
            raise CityNotFoundError(f"City '{city_clean}' not found.")

        if response.status_code == 429:
            logger.error("AccuWeather API rate limit exceeded")
            raise WeatherRateLimitError("AccuWeather API rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("AccuWeather service unavailable (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("AccuWeather service is temporarily unavailable.")

        if response.status_code != 200:
            logger.error("AccuWeather location search returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from AccuWeather location service.")

        try:
            results = response.json()
        except Exception as exc:
            logger.error("Failed to parse AccuWeather location JSON: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON received from AccuWeather location service.") from exc

        if not isinstance(results, list) or len(results) == 0:
            logger.warning("No location results found for city: %s", city_clean)
            raise CityNotFoundError(f"City '{city_clean}' not found.")

        first_match = results[0]
        location_key = str(first_match.get("Key", "")).strip()
        if not location_key:
            logger.error("AccuWeather location result has no Key: %s", first_match)
            raise WeatherResponseParsingError("Malformed location key received from AccuWeather.")

        localized_name = first_match.get("LocalizedName", city_clean)
        admin_area = first_match.get("AdministrativeArea", {}).get("LocalizedName", "")
        country = first_match.get("Country", {}).get("LocalizedName", "")
        geo = first_match.get("GeoPosition", {})

        location_info = {
            "key": location_key,
            "city": localized_name,
            "administrative_area": admin_area,
            "country": country,
            "latitude": float(geo.get("Latitude", 0.0)) if geo.get("Latitude") is not None else 0.0,
            "longitude": float(geo.get("Longitude", 0.0)) if geo.get("Longitude") is not None else 0.0,
            "formatted_address": f"{localized_name}, {admin_area}, {country}".strip(", "),
        }

        # Cache location key
        self._location_cache[cache_key] = location_info
        return location_info

    def get_historical_conditions(self, location_key: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Retrieve recent past hourly historical conditions from AccuWeather.
        
        Uses AccuWeather's 24-hour historical current conditions endpoint:
        GET /currentconditions/v1/{locationKey}/historical/24
        
        Args:
            location_key: AccuWeather location key string
            hours: Number of hours (supports up to 24 via Core Weather API)
            
        Returns:
            List of raw hourly condition observation dictionaries.
        """
        if not self.api_key:
            logger.error("AccuWeather API key is not configured")
            raise WeatherAuthenticationError("AccuWeather API key is not configured.")

        safe_hours = 24 if hours >= 12 else 24  # Core API standard endpoint is /historical/24

        url = f"{self.base_url}/currentconditions/v1/{location_key}/historical/{safe_hours}"
        params = {
            "apikey": self.api_key,
            "details": "true",
        }

        logger.debug("Requesting AccuWeather historical conditions for location_key: %s", location_key)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("AccuWeather historical conditions request timed out")
            raise WeatherTimeoutError("AccuWeather historical request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Network error connecting to AccuWeather historical API: %s", exc)
            raise WeatherServiceUnavailableError("Unable to reach AccuWeather service.") from exc

        if response.status_code in (401, 403):
            logger.error("AccuWeather authentication failed (HTTP %s)", response.status_code)
            raise WeatherAuthenticationError("AccuWeather service authentication failed.")

        if response.status_code == 404:
            logger.warning("AccuWeather location key %s not found (404)", location_key)
            raise CityNotFoundError(f"Location key '{location_key}' not found.")

        if response.status_code == 429:
            logger.error("AccuWeather rate limit exceeded")
            raise WeatherRateLimitError("AccuWeather API rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("AccuWeather provider error (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("AccuWeather service is temporarily unavailable.")

        if response.status_code != 200:
            logger.error("AccuWeather historical endpoint returned unexpected status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from AccuWeather.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse AccuWeather historical JSON: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON from AccuWeather service.") from exc

        if not isinstance(payload, list):
            logger.error("Unexpected AccuWeather historical response format (not a list): %s", type(payload))
            raise WeatherResponseParsingError("Unexpected data format received from AccuWeather.")

        return payload
