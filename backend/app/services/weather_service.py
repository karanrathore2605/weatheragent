"""Weather service layer containing domain logic and data normalization."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.clients.open_meteo_client import OpenMeteoClient
from app.clients.weather_client import (
    AmbiguousLocationError,
    CityNotFoundError,
    GoogleWeatherClient,
    WeatherAuthenticationError,
    WeatherClientError,
    WeatherServiceUnavailableError,
)
from app.repositories.weather_observation_repository import WeatherObservationRepository
from app.schemas.weather_schema import ForecastDay, ForecastResponse, WeatherResponse
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherService:
    """Business service coordinating weather retrieval and response normalization.
    
    Architecture Rule:
    - Service calls Client.
    - Service performs business validation and normalization.
    - Router calls Service.
    """

    def __init__(
        self,
        client: Optional[GoogleWeatherClient] = None,
        fallback_client: Optional[Any] = None,
        repository: Optional[WeatherObservationRepository] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        self.client = client or GoogleWeatherClient()
        if client is None and fallback_client is None:
            self.fallback_client = OpenMeteoClient()
        else:
            self.fallback_client = fallback_client
        self.repository = repository
        self.llm_service = llm_service or LLMService()

    def validate_city_input(self, city: str) -> str:
        """Validate requested city name string.
        
        Raises:
            ValueError: If city is empty, whitespace-only, or invalid.
        """
        if not city or not city.strip():
            logger.warning("Empty or whitespace-only city parameter provided")
            raise ValueError("City name cannot be empty.")

        trimmed = city.strip()

        if len(trimmed) < 2:
            logger.warning("City name too short: '%s'", trimmed)
            raise ValueError("City name must be at least 2 characters long.")

        # Ensure city name contains at least one alphabetic letter
        if not re.search(r"[a-zA-Z]", trimmed):
            logger.warning("City name has no alphabetic characters: '%s'", trimmed)
            raise ValueError("City name must contain alphabetic characters.")

        return trimmed

    def validate_forecast_days(self, days: int) -> int:
        """Validate requested forecast days parameter.
        
        Raises:
            ValueError: If days is not a positive integer between 1 and 10.
        """
        if not isinstance(days, int):
            try:
                days = int(days)
            except (ValueError, TypeError):
                raise ValueError("Forecast days must be an integer.")

        if days < 1 or days > 10:
            logger.warning("Invalid forecast days requested: %s", days)
            raise ValueError("Forecast days must be between 1 and 10.")

        return days

    def normalize_weather_data(
        self,
        city_name: str,
        location: Dict[str, Any],
        raw_conditions: Dict[str, Any],
    ) -> WeatherResponse:
        """Normalize raw provider data into canonical WeatherResponse schema."""
        logger.debug("Normalizing weather data for: %s", city_name)

        # 1. Temperature extraction
        temp_obj = raw_conditions.get("temperature", {})
        if isinstance(temp_obj, dict):
            raw_temp = temp_obj.get("degrees", 0.0)
        else:
            raw_temp = temp_obj or 0.0

        # 2. Feels like extraction
        feels_obj = raw_conditions.get("feelsLikeTemperature", {})
        if isinstance(feels_obj, dict):
            raw_feels = feels_obj.get("degrees", raw_temp)
        else:
            raw_feels = feels_obj or raw_temp

        # 3. Humidity extraction
        raw_humidity = raw_conditions.get("relativeHumidity", 0)

        # 4. Wind speed extraction (km/h)
        wind_obj = raw_conditions.get("wind", {})
        if isinstance(wind_obj, dict):
            speed_obj = wind_obj.get("speed", {})
            if isinstance(speed_obj, dict):
                raw_wind = speed_obj.get("value", 0.0)
            else:
                raw_wind = speed_obj or 0.0
        else:
            raw_wind = 0.0

        # 5. Condition text extraction
        cond_obj = raw_conditions.get("weatherCondition", {})
        if isinstance(cond_obj, dict):
            desc_obj = cond_obj.get("description", {})
            if isinstance(desc_obj, dict):
                condition_text = desc_obj.get("text", "Clear")
            else:
                condition_text = str(desc_obj or "Clear")
        elif isinstance(cond_obj, str):
            condition_text = cond_obj
        else:
            condition_text = "Clear"

        # 6. Observation timestamp
        observed_at = raw_conditions.get("currentTime")
        if not observed_at:
            observed_at = datetime.now(timezone.utc).isoformat()
        else:
            observed_at = str(observed_at)

        # 7. Cloud cover
        raw_cloud = raw_conditions.get("cloudCover")
        if raw_cloud is None:
            raw_cloud = raw_conditions.get("cloud_cover")
        cloud_val = None
        if isinstance(raw_cloud, dict):
            cloud_val = raw_cloud.get("percentage") or raw_cloud.get("value")
        elif raw_cloud is not None:
            try:
                cloud_val = int(raw_cloud)
            except (ValueError, TypeError):
                cloud_val = None

        # 8. UV index
        raw_uv = raw_conditions.get("uvIndex")
        if raw_uv is None:
            raw_uv = raw_conditions.get("uv_index")
        uv_val = None
        if isinstance(raw_uv, dict):
            uv_val = raw_uv.get("value")
        elif raw_uv is not None:
            try:
                uv_val = round(float(raw_uv), 1)
            except (ValueError, TypeError):
                uv_val = None

        # 9. Visibility in km
        raw_vis = raw_conditions.get("visibility")
        vis_val = None
        if isinstance(raw_vis, dict):
            dist = raw_vis.get("distance")
            if isinstance(dist, dict):
                vis_val = dist.get("value")
            elif dist is not None:
                vis_val = dist
            else:
                vis_val = raw_vis.get("value")
        elif raw_vis is not None:
            vis_val = raw_vis
        if vis_val is not None:
            try:
                v_num = float(vis_val)
                if v_num > 100:  # Reported in meters, convert to km
                    vis_val = round(v_num / 1000.0, 1)
                else:
                    vis_val = round(v_num, 1)
            except (ValueError, TypeError):
                vis_val = None

        # 10. Precipitation in mm
        raw_precip = raw_conditions.get("precipitation")
        precip_val = None
        if isinstance(raw_precip, dict):
            precip_val = raw_precip.get("qpf", {}).get("quantity") or raw_precip.get("value")
        elif raw_precip is not None:
            try:
                precip_val = round(float(raw_precip), 1)
            except (ValueError, TypeError):
                precip_val = None

        formatted_address = location.get("formatted_address", city_name)
        primary_city = formatted_address.split(",")[0].strip() if formatted_address else city_name

        return WeatherResponse(
            city=primary_city or city_name,
            temperature=round(float(raw_temp), 1),
            feels_like=round(float(raw_feels), 1),
            humidity=int(raw_humidity),
            wind_speed=round(float(raw_wind), 1),
            condition=condition_text or "Clear",
            observed_at=observed_at,
            resolved_address=formatted_address,
            cloud_cover=cloud_val,
            uv_index=uv_val,
            visibility=vis_val,
            precipitation=precip_val,
        )

    def normalize_forecast_data(
        self,
        city_name: str,
        location: Dict[str, Any],
        raw_forecast: Dict[str, Any],
        requested_days: int,
    ) -> ForecastResponse:
        """Normalize raw provider forecast data into canonical ForecastResponse schema."""
        logger.debug("Normalizing forecast data for: %s (days=%s)", city_name, requested_days)

        raw_days = raw_forecast.get("forecastDays") or raw_forecast.get("forecast") or []
        forecast_items: List[ForecastDay] = []

        for item in raw_days[:requested_days]:
            # Extract date
            interval = item.get("interval", {})
            start_time = interval.get("startTime") if isinstance(interval, dict) else None
            date_str = item.get("date") or (start_time[:10] if start_time else "")
            if not date_str:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            daytime = item.get("daytimeForecast", {})
            if not isinstance(daytime, dict):
                daytime = {}

            # Temperatures
            temp_obj = daytime.get("temperature") or item.get("temperature") or {}
            if isinstance(temp_obj, dict):
                min_t = temp_obj.get("min", item.get("temperature_min", 20.0))
                max_t = temp_obj.get("max", item.get("temperature_max", 30.0))
            else:
                min_t = item.get("temperature_min", 20.0)
                max_t = item.get("temperature_max", 30.0)

            # Condition
            cond_obj = daytime.get("weatherCondition") or item.get("weatherCondition") or {}
            if isinstance(cond_obj, dict):
                desc_obj = cond_obj.get("description", {})
                if isinstance(desc_obj, dict):
                    cond_text = desc_obj.get("text", item.get("condition", "Sunny"))
                else:
                    cond_text = str(desc_obj or item.get("condition", "Sunny"))
            elif isinstance(cond_obj, str):
                cond_text = cond_obj
            else:
                cond_text = item.get("condition", "Sunny")

            # Precipitation probability
            precip_obj = daytime.get("precipitation") or item.get("precipitation") or {}
            if isinstance(precip_obj, dict):
                p_prob = precip_obj.get("probability", item.get("precipitation_probability", 0))
            else:
                p_prob = item.get("precipitation_probability", 0)

            # Convert 0.2 to 20 if decimal
            if isinstance(p_prob, (int, float)):
                if 0.0 < float(p_prob) <= 1.0:
                    p_prob = int(round(float(p_prob) * 100))
                else:
                    p_prob = int(p_prob)
            else:
                p_prob = 0

            # Humidity
            hum_obj = daytime.get("humidity") or item.get("humidity") or {}
            if isinstance(hum_obj, dict):
                humidity_val = hum_obj.get("relative", item.get("humidity", 50))
            else:
                humidity_val = daytime.get("relativeHumidity", item.get("humidity", 50))

            # Wind speed
            wind_obj = daytime.get("wind") or item.get("wind") or {}
            if isinstance(wind_obj, dict):
                speed_val = wind_obj.get("speed", {})
                if isinstance(speed_val, dict):
                    wind_speed_val = speed_val.get("value", item.get("wind_speed", 10.0))
                else:
                    wind_speed_val = speed_val if speed_val is not None else item.get("wind_speed", 10.0)
            else:
                wind_speed_val = item.get("wind_speed", 10.0)

            forecast_items.append(
                ForecastDay(
                    date=date_str,
                    temperature_min=round(float(min_t or 0.0), 1),
                    temperature_max=round(float(max_t or 0.0), 1),
                    condition=str(cond_text or "Clear"),
                    precipitation_probability=int(p_prob),
                    humidity=int(humidity_val or 0),
                    wind_speed=round(float(wind_speed_val or 0.0), 1),
                )
            )

        formatted_address = location.get("formatted_address", city_name)
        primary_city = formatted_address.split(",")[0].strip() if formatted_address else city_name

        return ForecastResponse(
            city=primary_city or city_name,
            forecast=forecast_items,
            resolved_address=formatted_address,
        )

    def _persist_observation(
        self,
        weather_resp: WeatherResponse,
        location: Dict[str, Any],
        raw_conditions: Dict[str, Any],
        source: str = "google",
    ) -> None:
        """Persist weather observation for statistics tracking if repository is configured.
        
        Uses deduplication based on city and observation timestamp.
        Failures are safely logged and will never break current-weather queries.
        """
        if self.repository is None:
            return

        try:
            observed_str = weather_resp.observed_at
            try:
                observed_dt = datetime.fromisoformat(observed_str.replace("Z", "+00:00"))
            except Exception:
                observed_dt = datetime.now(timezone.utc)

            # Extract precipitation if provided
            precip = 0.0
            if "precipitation" in raw_conditions and isinstance(raw_conditions["precipitation"], dict):
                precip = float(raw_conditions["precipitation"].get("amount", 0.0) or 0.0)
            elif "precipitation" in raw_conditions and isinstance(raw_conditions["precipitation"], (int, float)):
                precip = float(raw_conditions["precipitation"])

            pressure = None
            if "pressure" in raw_conditions and isinstance(raw_conditions["pressure"], dict):
                pressure = float(raw_conditions["pressure"].get("value", 0.0) or 0.0)
            elif "pressure" in raw_conditions and isinstance(raw_conditions["pressure"], (int, float)):
                pressure = float(raw_conditions["pressure"])

            self.repository.save_observation({
                "city": weather_resp.city,
                "latitude": float(location.get("latitude", 0.0)),
                "longitude": float(location.get("longitude", 0.0)),
                "observed_at": observed_dt,
                "temperature": float(weather_resp.temperature),
                "feels_like_temperature": float(weather_resp.feels_like),
                "humidity": float(weather_resp.humidity),
                "precipitation": precip,
                "wind_speed": float(weather_resp.wind_speed),
                "pressure": pressure,
                "weather_condition": weather_resp.condition,
                "source": source,
            })
        except Exception as exc:
            logger.warning("Could not persist weather observation for city '%s': %s", weather_resp.city, exc)

    def resolve_city_coordinates(self, city: str) -> Dict[str, Any]:
        """Resolve city name to geographical coordinates using existing geocoding logic."""
        try:
            return self.client.geocode_city(city)
        except (AmbiguousLocationError, CityNotFoundError):
            raise
        except (WeatherAuthenticationError, WeatherServiceUnavailableError, WeatherClientError):
            if self.fallback_client is not None:
                logger.info("Resolving coordinates for '%s' using existing geocoding logic", city)
                return self.fallback_client.geocode_city(city)
            raise

    def get_current_weather(self, city: str) -> WeatherResponse:
        """Execute full flow: validate -> geocode -> fetch conditions from Google Weather API -> normalize."""
        valid_city = self.validate_city_input(city)

        logger.info("Resolving current weather for city: %s via Google Weather API", valid_city)

        # Step 1: Geocode city to coordinates using existing geocoding logic
        location = self.resolve_city_coordinates(valid_city)

        # Step 2: Query live conditions from Google Weather API (Single Source for Current Weather)
        raw_conditions = self.client.get_current_conditions(
            latitude=location["latitude"],
            longitude=location["longitude"],
        )

        # Step 3: Normalize to canonical schema
        res = self.normalize_weather_data(
            city_name=valid_city,
            location=location,
            raw_conditions=raw_conditions,
        )

        # Step 4: Persist observation for statistics
        self._persist_observation(res, location, raw_conditions, source="google")

        # Step 5: Attach AI meteorological summary
        self._attach_current_weather_summary(res)

        return res

    def _attach_current_weather_summary(self, weather_resp: WeatherResponse) -> None:
        """Enrich WeatherResponse with AI meteorological summary, failing gracefully if unavailable."""
        try:
            summary = self.llm_service.generate_current_weather_summary(
                city=weather_resp.city,
                weather_data=weather_resp.model_dump(),
                raise_on_error=False,
            )
            if summary:
                weather_resp.summary = summary
                weather_resp.summary_status = "SUCCESS"
                weather_resp.summary_message = None
            else:
                weather_resp.summary = None
                weather_resp.summary_status = "UNAVAILABLE"
                weather_resp.summary_message = "Weather summary is currently unavailable. Current weather data is shown above."
        except Exception as exc:
            logger.warning("Error generating current weather summary for '%s': %s", weather_resp.city, exc)
            weather_resp.summary = None
            weather_resp.summary_status = "UNAVAILABLE"
            weather_resp.summary_message = "Weather summary is currently unavailable. Current weather data is shown above."

    def get_forecast(self, city: str, days: int = 5) -> ForecastResponse:
        """Execute full forecast flow: validate -> geocode -> fetch forecast -> normalize."""
        valid_city = self.validate_city_input(city)
        valid_days = self.validate_forecast_days(days)

        logger.info("Resolving %s-day weather forecast for city: %s", valid_days, valid_city)

        # Step 1: Geocode city to coordinates using existing geocoding logic
        location = self.resolve_city_coordinates(valid_city)

        try:
            # Step 2: Query multi-day forecast using coordinates
            raw_forecast = self.client.get_forecast(
                latitude=location["latitude"],
                longitude=location["longitude"],
                days=valid_days,
            )

            # Step 3: Normalize to canonical ForecastResponse
            return self.normalize_forecast_data(
                city_name=valid_city,
                location=location,
                raw_forecast=raw_forecast,
                requested_days=valid_days,
            )
        except (WeatherAuthenticationError, WeatherServiceUnavailableError) as exc:
            if self.fallback_client is not None:
                logger.warning(
                    "Primary weather provider unavailable (%s). Falling back to Open-Meteo for forecast: %s",
                    exc,
                    valid_city,
                )
                raw_forecast = self.fallback_client.get_forecast(
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    days=valid_days,
                )
                return self.normalize_forecast_data(
                    city_name=valid_city,
                    location=location,
                    raw_forecast=raw_forecast,
                    requested_days=valid_days,
                )
            raise
