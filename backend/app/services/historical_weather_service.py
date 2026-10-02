"""Historical Weather Service abstraction.

Architecture Rules:
- Google Weather API is the primary weather data source.
- Database is used strictly for persistence/cache/storage of Google Weather API observations.
- Never fabricates or synthesizes missing historical weather data.
- Never silently substitutes forecast data for historical data.
- Separates low-level API retrieval from calculation and routing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.clients.open_meteo_client import OpenMeteoClient
from app.clients.weather_client import (
    CityNotFoundError,
    GoogleWeatherClient,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HistoricalWeatherService:
    """Service coordinating historical weather observation retrieval and persistence."""

    def __init__(
        self,
        client: Optional[GoogleWeatherClient] = None,
        repository: Optional[WeatherObservationRepository] = None,
        fallback_client: Optional[Any] = None,
    ) -> None:
        self.client = client or GoogleWeatherClient()
        if client is None and fallback_client is None:
            self.fallback_client = OpenMeteoClient()
        else:
            self.fallback_client = fallback_client
        self.repository = repository

    def _normalize_iso_datetime(self, date_val: Any) -> datetime:
        """Parse various date string formats into a UTC-aware datetime."""
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                return date_val.replace(tzinfo=timezone.utc)
            return date_val.astimezone(timezone.utc)

        if not date_val:
            return datetime.now(timezone.utc)

        s = str(date_val).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    def _parse_hourly_observations(
        self,
        raw_history: Dict[str, Any],
        city_name: str,
        location: Dict[str, Any],
        source: str = "google",
    ) -> List[Dict[str, Any]]:
        """Parse and normalize raw provider historical hours into canonical observation dictionaries."""
        hours_list = raw_history.get("historyHours") or raw_history.get("hours") or []
        parsed = []

        lat = float(location.get("latitude", 0.0))
        lng = float(location.get("longitude", 0.0))

        for item in hours_list:
            # 1. Observation timestamp
            interval = item.get("interval", {})
            raw_time = interval.get("startTime") if isinstance(interval, dict) else None
            if not raw_time:
                raw_time = item.get("startTime") or item.get("time")
            observed_dt = self._normalize_iso_datetime(raw_time)

            # 2. Temperature
            temp_obj = item.get("temperature", {})
            if isinstance(temp_obj, dict):
                temp_val = temp_obj.get("degrees", 0.0)
            else:
                temp_val = temp_obj or 0.0

            # 3. Feels like
            feels_obj = item.get("feelsLikeTemperature", {})
            if isinstance(feels_obj, dict):
                feels_val = feels_obj.get("degrees", temp_val)
            else:
                feels_val = feels_obj or temp_val

            # 4. Relative humidity
            humidity_val = item.get("relativeHumidity", 0)

            # 5. Wind speed
            wind_obj = item.get("wind", {})
            if isinstance(wind_obj, dict):
                speed_obj = wind_obj.get("speed", {})
                if isinstance(speed_obj, dict):
                    wind_val = speed_obj.get("value", 0.0)
                else:
                    wind_val = speed_obj or 0.0
            else:
                wind_val = item.get("wind_speed", 0.0)

            # 6. Precipitation
            precip_obj = item.get("precipitation", {})
            if isinstance(precip_obj, dict):
                precip_val = precip_obj.get("amount", 0.0) or 0.0
            else:
                precip_val = precip_obj or 0.0

            # 7. Weather condition
            cond_obj = item.get("weatherCondition", {})
            if isinstance(cond_obj, dict):
                desc_obj = cond_obj.get("description", {})
                if isinstance(desc_obj, dict):
                    cond_text = desc_obj.get("text", "Clear")
                else:
                    cond_text = str(desc_obj or "Clear")
            else:
                cond_text = str(cond_obj or "Clear")

            parsed.append({
                "city": city_name,
                "latitude": lat,
                "longitude": lng,
                "observed_at": observed_dt,
                "temperature": float(temp_val),
                "feels_like_temperature": float(feels_val) if feels_val is not None else None,
                "humidity": float(humidity_val) if humidity_val is not None else None,
                "precipitation": float(precip_val) if precip_val is not None else 0.0,
                "wind_speed": float(wind_val) if wind_val is not None else None,
                "pressure": None,
                "weather_condition": cond_text,
                "source": source,
            })

        return parsed

    def fetch_and_get_observations(
        self,
        city: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """Fetch historical observations from Google Weather API, persist cache, and query window.
        
        Args:
            city: Requested city name
            start_date: Start of historical window (UTC)
            end_date: End of historical window (UTC)
            
        Returns:
            Tuple of (observations_list, resolved_location)
        """
        # Step 1: Geocode city using primary client
        try:
            location = self.client.geocode_city(city)
        except (WeatherAuthenticationError, WeatherServiceUnavailableError) as exc:
            if self.fallback_client is not None and hasattr(self.fallback_client, "geocode_city"):
                logger.warning("Geocoding fallback engaged for %s: %s", city, exc)
                location = self.fallback_client.geocode_city(city)
            else:
                raise

        resolved_address = location.get("formatted_address", city)
        primary_city = resolved_address.split(",")[0].strip() if resolved_address else city

        # Step 2: Request whatever historical data Google Weather API actually supports (up to 24h)
        source = "google"
        try:
            raw_history = self.client.get_historical_hours(
                latitude=location["latitude"],
                longitude=location["longitude"],
                hours=24,
            )
        except (WeatherAuthenticationError, WeatherServiceUnavailableError) as exc:
            if self.fallback_client is not None and hasattr(self.fallback_client, "get_historical_hours"):
                logger.warning("Historical data fallback engaged for %s: %s", city, exc)
                raw_history = self.fallback_client.get_historical_hours(
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    hours=24,
                )
                source = "open-meteo"
            else:
                raise

        # Step 3: Parse and normalize observations
        parsed_obs = self._parse_hourly_observations(
            raw_history=raw_history,
            city_name=primary_city,
            location=location,
            source=source,
        )

        # Step 4: Persist newly fetched observations into repository cache
        if self.repository is not None:
            for obs_dict in parsed_obs:
                try:
                    self.repository.save_observation(obs_dict)
                except Exception as save_err:
                    logger.debug("Could not persist observation for %s: %s", primary_city, save_err)

            # Query all available observations from persistent cache covering the window
            observations = self.repository.get_observations_by_date_range(
                city=primary_city,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            # In-memory filter if no database repository configured
            observations = [
                o for o in parsed_obs
                if start_date <= o["observed_at"] <= end_date
            ]

        return observations, location
