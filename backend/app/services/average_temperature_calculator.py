"""Average temperature calculation service.

Architecture Rules:
- Pure calculation logic only (no I/O, no DB, no network, no LLMs).
- Calculates average temperature in degrees Celsius.
- Strictly deterministic, rounds to 1 decimal place.
- Never fabricates missing or fake values.
- Gracefully ignores null/missing temperature values.
"""

from typing import Any, List, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AverageTemperatureCalculator:
    """Specialized calculator computing average temperature from observations."""

    @staticmethod
    def calculate_average_temperature(observations: List[Any]) -> Optional[float]:
        """Compute the average temperature in Celsius from weather observations.
        
        Args:
            observations: List of observation dictionaries or models.
            
        Returns:
            Float rounded to 1 decimal place, or None if no valid temperature values exist.
        """
        if not observations:
            logger.debug("No observations provided to AverageTemperatureCalculator")
            return None

        temps: List[float] = []
        for obs in observations:
            val = None
            if isinstance(obs, dict):
                val = obs.get("temperature")
            else:
                val = getattr(obs, "temperature", None)

            if val is not None:
                try:
                    temps.append(float(val))
                except (ValueError, TypeError):
                    continue

        if not temps:
            logger.debug("No valid numerical temperature entries found in observations")
            return None

        avg_temp = round(sum(temps) / len(temps), 1)
        return avg_temp
