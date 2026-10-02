"""Deterministic meteorological statistics calculator.

Architecture Rules:
- Pure calculation logic only (no I/O, no DB, no network, no LLMs).
- Strict numerical calculations: average, min, max, total.
- Never fabricates missing or fake values.
- Gracefully ignores null/missing values during aggregations.
"""

from typing import Any, Dict, List, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StatisticsCalculator:
    """Production meteorological statistics calculator."""

    @staticmethod
    def calculate(observations: List[Any]) -> Dict[str, Optional[float]]:
        """Calculate deterministic weather statistics from a collection of observations.
        
        Args:
            observations: List of WeatherObservation models or dicts.
            
        Returns:
            Dict containing calculated metrics rounded to 1 decimal place.
        """
        if not observations:
            logger.debug("No observations provided to StatisticsCalculator")
            return {
                "average_temperature": None,
                "minimum_temperature": None,
                "maximum_temperature": None,
                "average_feels_like_temperature": None,
                "average_humidity": None,
                "average_wind_speed": None,
                "total_precipitation": 0.0,
            }

        def _get_val(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # 1. Temperatures
        raw_temps = [_get_val(obs, "temperature") for obs in observations]
        temps = [float(t) for t in raw_temps if t is not None]

        # 2. Feels like temperatures
        raw_feels = [_get_val(obs, "feels_like_temperature") for obs in observations]
        feels = [float(f) for f in raw_feels if f is not None]

        # 3. Humidities
        raw_humidity = [_get_val(obs, "humidity") for obs in observations]
        humidities = [float(h) for h in raw_humidity if h is not None]

        # 4. Wind speeds
        raw_wind = [_get_val(obs, "wind_speed") for obs in observations]
        winds = [float(w) for w in raw_wind if w is not None]

        # 5. Precipitations
        raw_precip = [_get_val(obs, "precipitation") for obs in observations]
        precips = [float(p) for p in raw_precip if p is not None]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        min_temp = round(min(temps), 1) if temps else None
        max_temp = round(max(temps), 1) if temps else None

        avg_feels = round(sum(feels) / len(feels), 1) if feels else None
        avg_hum = round(sum(humidities) / len(humidities), 1) if humidities else None
        avg_wind = round(sum(winds) / len(winds), 1) if winds else None
        total_precip = round(sum(precips), 1) if precips else 0.0

        return {
            "average_temperature": avg_temp,
            "minimum_temperature": min_temp,
            "maximum_temperature": max_temp,
            "average_feels_like_temperature": avg_feels,
            "average_humidity": avg_hum,
            "average_wind_speed": avg_wind,
            "total_precipitation": total_precip,
        }
