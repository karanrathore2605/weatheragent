"""Historical Weather Service abstraction integrating with AccuWeather.

Architecture Rules:
- AccuWeather is the primary weather data provider for historical statistics.
- Resolves city location keys via AccuWeather Locations API.
- Retrieves available historical conditions from AccuWeather.
- Database is used strictly for persistence/cache of AccuWeather observations.
- Never fabricates or synthesizes missing historical weather data.
- Never silently substitutes forecast data for historical data.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.clients.accuweather_client import AccuWeatherClient
from app.clients.weather_client import (
    CityNotFoundError,
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
    """Service coordinating historical weather observation retrieval from AccuWeather and caching."""

    def __init__(
        self,
        accuweather_client: Optional[AccuWeatherClient] = None,
        repository: Optional[WeatherObservationRepository] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.client = accuweather_client or client or AccuWeatherClient()
        self.repository = repository

    def _normalize_iso_datetime(self, date_val: Any) -> datetime:
        """Parse various date formats into a UTC-aware datetime."""
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                return date_val.replace(tzinfo=timezone.utc)
            return date_val.astimezone(timezone.utc)

        if isinstance(date_val, (int, float)):
            try:
                return datetime.fromtimestamp(date_val, tz=timezone.utc)
            except Exception:
                return datetime.now(timezone.utc)

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

    def _parse_accuweather_observations(
        self,
        raw_items: List[Dict[str, Any]],
        city_name: str,
        location: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Parse raw AccuWeather historical current conditions array into canonical observation dicts."""
        parsed = []
        lat = float(location.get("latitude", 0.0))
        lng = float(location.get("longitude", 0.0))

        for item in raw_items:
            # 1. Observation timestamp
            raw_time = item.get("LocalObservationDateTime")
            epoch_time = item.get("EpochTime")
            if raw_time:
                observed_dt = self._normalize_iso_datetime(raw_time)
            elif epoch_time is not None:
                observed_dt = self._normalize_iso_datetime(epoch_time)
            else:
                observed_dt = datetime.now(timezone.utc)

            # 2. Temperature in Celsius
            temp_obj = item.get("Temperature", {})
            metric_temp = temp_obj.get("Metric", {}) if isinstance(temp_obj, dict) else {}
            temp_val = metric_temp.get("Value") if isinstance(metric_temp, dict) else None
            if temp_val is None:
                # Direct value fallback if already flattened
                temp_val = item.get("temperature", 0.0)

            # 3. Feels like temperature
            real_feel = item.get("RealFeelTemperature", {})
            metric_feel = real_feel.get("Metric", {}) if isinstance(real_feel, dict) else {}
            feel_val = metric_feel.get("Value") if isinstance(metric_feel, dict) else None

            # 4. Relative humidity
            humidity = item.get("RelativeHumidity")

            # 5. Condition text
            condition_text = item.get("WeatherText", "Clear")

            parsed.append({
                "city": city_name,
                "latitude": lat,
                "longitude": lng,
                "observed_at": observed_dt,
                "temperature": float(temp_val) if temp_val is not None else 0.0,
                "feels_like_temperature": float(feel_val) if feel_val is not None else None,
                "humidity": float(humidity) if humidity is not None else None,
                "precipitation": 0.0,
                "wind_speed": None,
                "pressure": None,
                "weather_condition": str(condition_text),
                "source": "accuweather",
            })

        return parsed

    def fetch_and_get_observations(
        self,
        city: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """Fetch historical observations from AccuWeather, persist cache, and query window.
        
        Args:
            city: Requested city name
            start_date: Start of historical window (UTC)
            end_date: End of historical window (UTC)
            
        Returns:
            Tuple of (observations_list, resolved_location)
        """
        # Step 1: Resolve city to AccuWeather location key
        location = self.client.search_location(city)
        location_key = location["key"]
        city_name = location.get("city", city)

        # Step 2: Request historical conditions from AccuWeather (past 24h supported via Core API)
        raw_history = self.client.get_historical_conditions(location_key=location_key, hours=24)

        # Step 3: Parse and normalize observations
        parsed_obs = self._parse_accuweather_observations(
            raw_items=raw_history,
            city_name=city_name,
            location=location,
        )

        # Step 4: Persist newly fetched observations into repository cache
        if self.repository is not None:
            for obs_dict in parsed_obs:
                try:
                    self.repository.save_observation(obs_dict)
                except Exception as save_err:
                    logger.debug("Could not persist observation for %s: %s", city_name, save_err)

            # Query all available observations from persistent cache covering the window
            observations = self.repository.get_observations_by_date_range(
                city=city_name,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            observations = [
                o for o in parsed_obs
                if start_date <= o["observed_at"] <= end_date
            ]

        return observations, location
