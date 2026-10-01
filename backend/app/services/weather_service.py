"""Weather service layer containing domain logic and data normalization."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.clients.weather_client import GoogleWeatherClient
from app.schemas.weather_schema import WeatherResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherService:
    """Business service coordinating weather retrieval and response normalization.
    
    Architecture Rule:
    - Service calls Client.
    - Service performs business validation and normalization.
    - Router calls Service.
    """

    def __init__(self, client: Optional[GoogleWeatherClient] = None) -> None:
        self.client = client or GoogleWeatherClient()

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
            # Clean trailing Z for standardized formatting if desired
            observed_at = str(observed_at)

        # Extract primary city label from formatted address if available
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
        )

    def get_current_weather(self, city: str) -> WeatherResponse:
        """Execute full flow: validate -> geocode -> fetch conditions -> normalize."""
        valid_city = self.validate_city_input(city)

        logger.info("Resolving current weather for city: %s", valid_city)

        # Step 1: Geocode city to coordinates
        location = self.client.geocode_city(valid_city)

        # Step 2: Query current conditions using coordinates
        raw_conditions = self.client.get_current_conditions(
            latitude=location["latitude"],
            longitude=location["longitude"],
        )

        # Step 3: Normalize to canonical schema
        return self.normalize_weather_data(
            city_name=valid_city,
            location=location,
            raw_conditions=raw_conditions,
        )
