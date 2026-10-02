"""Open-Meteo external weather client providing free global forecasts and geocoding."""

from typing import Any, Dict, Optional
import httpx

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherClientError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    62: "Moderate rain",
    63: "Heavy rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class OpenMeteoClient:
    """Free weather client using Open-Meteo API.
    
    Requires no API keys, billing, or subscription.
    """

    def __init__(
        self,
        timeout: float = 10.0,
        geocoding_base_url: str = "https://geocoding-api.open-meteo.com/v1/search",
        weather_base_url: str = "https://api.open-meteo.com/v1/forecast",
    ) -> None:
        self.timeout = timeout
        self.geocoding_base_url = geocoding_base_url
        self.weather_base_url = weather_base_url

    def geocode_city(self, city: str) -> Dict[str, Any]:
        """Convert a city name into geographical coordinates using Open-Meteo Geocoding API."""
        params = {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        }
        logger.debug("Open-Meteo geocoding for city: %s", city)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.geocoding_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo geocoding timed out for city: %s", city)
            raise WeatherTimeoutError("Geocoding request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo network error during geocoding: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to connect to location service.") from exc

        if response.status_code != 200:
            logger.error("Open-Meteo geocoding returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Location service returned an error.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Open-Meteo geocoding JSON")
            raise WeatherResponseParsingError("Invalid response format from location service.") from exc

        results = payload.get("results")
        if not results:
            logger.warning("City '%s' not found via Open-Meteo", city)
            raise CityNotFoundError(f"City '{city}' not found.")

        item = results[0]
        name = item.get("name", city)
        admin1 = item.get("admin1")
        country = item.get("country")
        parts = [p for p in (name, admin1, country) if p]
        formatted_address = ", ".join(parts) if parts else city

        return {
            "latitude": float(item["latitude"]),
            "longitude": float(item["longitude"]),
            "formatted_address": formatted_address,
        }

    def get_current_conditions(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Fetch current weather conditions from Open-Meteo."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        }
        logger.debug("Open-Meteo requesting current conditions for lat=%s, lng=%s", latitude, longitude)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.weather_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo request timed out")
            raise WeatherTimeoutError("Weather service request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo network error: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to reach weather service.") from exc

        if response.status_code != 200:
            logger.error("Open-Meteo returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Weather service returned an error.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Open-Meteo JSON response: %s", exc)
            raise WeatherResponseParsingError("Invalid response format from weather service.") from exc

        current = payload.get("current", {})
        weather_code = current.get("weather_code", 0)
        condition_text = WMO_WEATHER_CODES.get(weather_code, "Clear")

        return {
            "currentTime": current.get("time"),
            "temperature": {"degrees": current.get("temperature_2m", 0.0)},
            "feelsLikeTemperature": {"degrees": current.get("apparent_temperature", 0.0)},
            "relativeHumidity": int(current.get("relative_humidity_2m", 0)),
            "wind": {"speed": {"value": current.get("wind_speed_10m", 0.0)}},
            "weatherCondition": {"description": {"text": condition_text}},
        }

    def get_forecast(self, latitude: float, longitude: float, days: int = 5) -> Dict[str, Any]:
        """Fetch multi-day weather forecast from Open-Meteo."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,relative_humidity_2m_mean,wind_speed_10m_max",
            "timezone": "auto",
            "forecast_days": days,
        }
        logger.debug("Open-Meteo requesting forecast for lat=%s, lng=%s, days=%s", latitude, longitude, days)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.weather_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo forecast timed out")
            raise WeatherTimeoutError("Weather forecast request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo network error: %s", str(exc))
            raise WeatherServiceUnavailableError("Unable to reach weather service.") from exc

        if response.status_code != 200:
            logger.error("Open-Meteo forecast returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Weather service returned an error.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Open-Meteo forecast JSON: %s", exc)
            raise WeatherResponseParsingError("Invalid JSON from weather service.") from exc

        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        temp_maxs = daily.get("temperature_2m_max", [])
        temp_mins = daily.get("temperature_2m_min", [])
        weather_codes = daily.get("weather_code", [])
        precip_probs = daily.get("precipitation_probability_max", [])
        humidities = daily.get("relative_humidity_2m_mean", [])
        wind_speeds = daily.get("wind_speed_10m_max", [])

        forecast_days = []
        for i, date_str in enumerate(dates[:days]):
            code = weather_codes[i] if i < len(weather_codes) else 0
            cond = WMO_WEATHER_CODES.get(code, "Clear")
            t_min = temp_mins[i] if i < len(temp_mins) else 20.0
            t_max = temp_maxs[i] if i < len(temp_maxs) else 30.0
            p_prob = precip_probs[i] if i < len(precip_probs) else 0
            hum = humidities[i] if i < len(humidities) else 50
            wind = wind_speeds[i] if i < len(wind_speeds) else 10.0

            forecast_days.append({
                "date": date_str,
                "temperature_min": t_min,
                "temperature_max": t_max,
                "condition": cond,
                "precipitation_probability": p_prob or 0,
                "humidity": hum or 0,
                "wind_speed": wind or 0.0,
            })

        return {"forecast": forecast_days}
