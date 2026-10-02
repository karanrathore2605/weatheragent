"""Historical Weather Service abstraction integrating with Open-Meteo Archive API.

Architecture Rules:
- Open-Meteo Historical Weather API is the primary provider for historical statistics.
- Resolves city coordinates and timezone via Open-Meteo Geocoding API.
- Retrieves daily mean temperatures from Open-Meteo Archive API.
- Never fabricates or synthesizes missing historical weather data.
- Database is not a required dependency for historical average calculations.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.services.weather.open_meteo_client import OpenMeteoClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HistoricalWeatherService:
    """Service coordinating historical weather data retrieval from Open-Meteo Archive API."""

    def __init__(
        self,
        open_meteo_client: Optional[OpenMeteoClient] = None,
        repository: Optional[WeatherObservationRepository] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.open_meteo_client = open_meteo_client or client or OpenMeteoClient()
        self.repository = repository

    def fetch_historical_temperatures(
        self,
        city: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Fetch daily historical temperatures for a city from Open-Meteo.

        Args:
            city: City name string (e.g. 'Indore', 'Delhi', 'Mumbai')
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)

        Returns:
            Dict containing resolved city name, coordinates, dates list, and temperatures list.
        """
        # Step 1: Resolve city to coordinates and timezone
        location = self.open_meteo_client.geocode_city(city)
        lat = location["latitude"]
        lng = location["longitude"]
        tz = location.get("timezone", "auto")
        city_name = location.get("city", city)

        # Step 2: Query Open-Meteo Archive API for daily mean temperatures
        raw_archive = self.open_meteo_client.get_historical_weather(
            latitude=lat,
            longitude=lng,
            start_date=start_date,
            end_date=end_date,
            timezone=tz,
        )

        dates = raw_archive.get("time", [])
        temperatures = raw_archive.get("temperature_2m_mean", [])

        logger.info(
            "Retrieved %d daily historical observations for city '%s' (%s to %s)",
            len(temperatures),
            city_name,
            start_date,
            end_date,
        )

        return {
            "city": city_name,
            "resolved_address": location.get("formatted_address"),
            "latitude": lat,
            "longitude": lng,
            "timezone": tz,
            "dates": dates,
            "temperatures": temperatures,
            "location": location,
        }

    def fetch_and_get_observations(
        self,
        city: str,
        start_date: Any,
        end_date: Any,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Legacy-compatible interface returning observation dicts and location info."""
        s_date_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)[:10]
        e_date_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)[:10]

        result = self.fetch_historical_temperatures(city, s_date_str, e_date_str)
        location = result["location"]
        dates = result["dates"]
        temps = result["temperatures"]

        observations = []
        for d, t in zip(dates, temps):
            if t is not None:
                observations.append({
                    "city": result["city"],
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "observed_at": d,
                    "temperature": float(t),
                    "source": "open-meteo",
                })

        return observations, location
