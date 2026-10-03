"""Open-Meteo Historical Weather API client.

Architecture Rules:
- Direct HTTP communication with Open-Meteo Geocoding and Archive APIs.
- Resolves city names to coordinates (latitude, longitude, timezone).
- Retrieves daily mean temperatures (temperature_2m_mean) over requested date windows.
- Free API: requires no API key.
- Strict error mapping (timeouts, rate limits, service unavailable, not found).
- Never leaks internal stack traces.
"""

from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional
import httpx

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenMeteoClient:
    """Client for Open-Meteo Geocoding and Historical Forecast/Archive APIs."""

    def __init__(
        self,
        timeout: float = 10.0,
        geocoding_base_url: str = "https://geocoding-api.open-meteo.com/v1/search",
        archive_base_url: str = "https://historical-forecast-api.open-meteo.com/v1/forecast",
        historical_weather_base_url: str = "https://archive-api.open-meteo.com/v1/archive",
    ) -> None:
        self.timeout = timeout
        self.geocoding_base_url = geocoding_base_url.rstrip("/")
        self.archive_base_url = archive_base_url.rstrip("/")
        self.historical_weather_base_url = historical_weather_base_url.rstrip("/")
        # In-memory geocoding cache: city_lower -> location dict
        self._location_cache: Dict[str, Dict[str, Any]] = {}

    def geocode_city(self, city: str) -> Dict[str, Any]:
        """Resolve a city name into geographical coordinates and timezone.

        Args:
            city: City name string (e.g. 'Indore', 'Delhi', 'Mumbai', 'London')

        Returns:
            Dict containing name, latitude, longitude, timezone, and formatted_address.

        Raises:
            CityNotFoundError: If city is empty or not found.
            WeatherTimeoutError: On request timeout.
            WeatherServiceUnavailableError: On network or server errors.
            WeatherResponseParsingError: On malformed response.
        """
        if not city or not city.strip():
            raise CityNotFoundError("City name cannot be empty.")

        city_clean = city.strip()
        from app.services.location_service import (
            INDIAN_CITY_ALIASES,
            format_location_address,
            normalize_name,
            select_best_candidate,
        )

        norm_city = normalize_name(city_clean)
        if norm_city in INDIAN_CITY_ALIASES:
            city_clean = INDIAN_CITY_ALIASES[norm_city]

        cache_key = city_clean.lower()

        if cache_key in self._location_cache:
            logger.debug("Open-Meteo geocoding cache hit for '%s'", city_clean)
            return self._location_cache[cache_key]

        params = {
            "name": city_clean,
            "count": 20,
            "language": "en",
            "format": "json",
        }

        logger.debug("Resolving coordinates for city '%s' via Open-Meteo Geocoding", city_clean)

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(self.geocoding_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo geocoding timed out for city: %s", city_clean)
            raise WeatherTimeoutError("Geocoding request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo network error during geocoding: %s", exc)
            raise WeatherServiceUnavailableError("Unable to connect to location service.") from exc

        if response.status_code == 404:
            logger.warning("Open-Meteo geocoding 404 for city: %s", city_clean)
            raise CityNotFoundError(f"City '{city_clean}' not found.")

        if response.status_code == 429:
            logger.error("Open-Meteo geocoding rate limit exceeded")
            raise WeatherRateLimitError("Geocoding service rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Open-Meteo geocoding service unavailable (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("Geocoding service is temporarily unavailable.")

        if response.status_code != 200:
            logger.error("Open-Meteo geocoding unexpected status %s", response.status_code)
            raise WeatherServiceUnavailableError("Location service returned an error.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Open-Meteo geocoding JSON: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON from location service.") from exc

        results = payload.get("results")
        if not results or not isinstance(results, list) or len(results) == 0:
            logger.warning("City '%s' not found via Open-Meteo geocoding", city_clean)
            raise CityNotFoundError(f"City '{city_clean}' not found.")

        best_match = select_best_candidate(city_clean, results)
        resolved_name = best_match.get("name", city_clean)
        admin1 = best_match.get("admin1", "")
        country = best_match.get("country", "")
        country_code = best_match.get("country_code", "")
        timezone_name = best_match.get("timezone", "Asia/Kolkata" if country_code == "IN" else "auto")

        formatted_address = format_location_address(
            name=resolved_name,
            admin1=admin1,
            country=country,
            country_code=country_code,
        )

        location_info = {
            "name": resolved_name,
            "city": resolved_name,
            "latitude": float(best_match["latitude"]),
            "longitude": float(best_match["longitude"]),
            "timezone": timezone_name,
            "country": country,
            "admin1": admin1,
            "formatted_address": formatted_address,
        }

        self._location_cache[cache_key] = location_info
        return location_info

    def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        timezone: str = "auto",
    ) -> Dict[str, Any]:
        """Fetch daily historical weather from Open-Meteo Archive API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            timezone: Location timezone string (e.g. 'Asia/Kolkata')

        Returns:
            Dict containing 'time' (dates list) and 'temperature_2m_mean' (temps list).

        Raises:
            WeatherTimeoutError: On request timeout.
            WeatherRateLimitError: On 429 quota exceeded.
            WeatherServiceUnavailableError: On network or 5xx server errors.
            WeatherResponseParsingError: On malformed JSON or unexpected schema.
        """
        today_str = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d")
        api_end_date = min(end_date, today_str)

        if start_date > api_end_date:
            logger.debug(
                "Requested start_date %s is in the future compared to max historical date %s",
                start_date,
                api_end_date,
            )
            return {
                "time": [],
                "temperature_2m_mean": [],
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone or "auto",
            }

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": api_end_date,
            "daily": "temperature_2m_mean",
            "timezone": timezone or "auto",
        }

        logger.debug(
            "Requesting Open-Meteo historical archive for lat=%s, lng=%s (%s to %s, tz=%s)",
            latitude,
            longitude,
            start_date,
            api_end_date,
            timezone,
        )

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(self.archive_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo archive request timed out")
            raise WeatherTimeoutError("Historical weather request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo network error connecting to archive API: %s", exc)
            raise WeatherServiceUnavailableError("Unable to reach historical weather service.") from exc

        if response.status_code == 429:
            logger.error("Open-Meteo archive API rate limit exceeded")
            raise WeatherRateLimitError("Historical weather API rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Open-Meteo archive service unavailable (HTTP %s)", response.status_code)
            raise WeatherServiceUnavailableError("Historical weather service is temporarily unavailable.")

        if response.status_code == 400:
            # Open-Meteo 400 usually indicates invalid dates or out of bounds coordinates
            logger.warning("Open-Meteo archive returned 400: %s", response.text)
            raise WeatherServiceUnavailableError("Historical weather parameters are invalid.")

        if response.status_code != 200:
            logger.error("Open-Meteo archive returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Unexpected response status from historical weather service.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Open-Meteo archive JSON: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON received from historical weather service.") from exc

        daily = payload.get("daily")
        if not isinstance(daily, dict):
            logger.error("Malformed Open-Meteo archive response (missing 'daily' object): %s", payload)
            raise WeatherResponseParsingError("Unexpected format from historical weather service.")

        dates = daily.get("time", [])
        mean_temps = daily.get("temperature_2m_mean", [])

        if not isinstance(dates, list) or not isinstance(mean_temps, list):
            logger.error("Malformed daily arrays in Open-Meteo response: %s", daily)
            raise WeatherResponseParsingError("Invalid daily data structure from historical weather service.")

        return {
            "time": dates,
            "temperature_2m_mean": mean_temps,
            "latitude": payload.get("latitude", latitude),
            "longitude": payload.get("longitude", longitude),
            "timezone": payload.get("timezone", timezone),
        }
