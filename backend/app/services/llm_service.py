"""LLM Service responsible for natural language generation and meteorological summarization."""

import re
from typing import Any, Dict, Optional

from app.clients.groq_client import BaseLLMClient, GroqClient, LLMClientError
from app.prompts.weather_prompts import (
    CURRENT_WEATHER_SUMMARY_SYSTEM_PROMPT,
    WEATHER_SUMMARY_SYSTEM_PROMPT,
    format_current_weather_payload,
    format_weather_summary_payload,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """Production service orchestrating LLM interactions for weather narrative generation.

    Architecture Rules:
    - Service delegates API requests to BaseLLMClient abstraction.
    - Does NOT perform numerical calculations.
    - Validates inputs and outputs strictly.
    - Gracefully handles provider downtime without crashing the host application.
    """

    def __init__(self, client: Optional[BaseLLMClient] = None) -> None:
        self.client = client or GroqClient()

    def generate_weather_summary(
        self,
        city: str,
        period: str,
        duration: int,
        statistics: Dict[str, Any],
        raise_on_error: bool = False,
    ) -> Optional[str]:
        """Generate a natural-language meteorological summary from calculated statistics.

        Args:
            city: Target city name.
            period: Aggregation period ('week', 'month').
            duration: Duration count (e.g. 2 for 2 weeks, 4 for 4 months).
            statistics: Dictionary of calculated metrics.
            raise_on_error: If True, re-raises LLMClientError instead of returning None.

        Returns:
            Clean summary text string if successful, or None on failure.
        """
        if not statistics:
            logger.warning("Empty statistics provided to LLMService; skipping generation.")
            return None

        # Build structured, injection-safe user payload
        payload = format_weather_summary_payload(
            city=city,
            period=period,
            duration=duration,
            statistics=statistics,
        )

        try:
            raw_summary = self.client.generate_completion(
                system_prompt=WEATHER_SUMMARY_SYSTEM_PROMPT,
                user_content=payload,
            )

            # Clean and sanitize summary output
            cleaned = self._clean_llm_output(raw_summary)
            if not cleaned:
                logger.warning("Sanitized LLM output is empty.")
                return None

            return cleaned

        except LLMClientError as exc:
            logger.warning("LLM generation failed for city='%s', period='%s', duration=%d: %s", city, period, duration, exc)
            if raise_on_error:
                raise
            return None
        except Exception as exc:
            logger.exception("Unexpected error during LLM generation for city='%s': %s", city, exc)
            if raise_on_error:
                raise LLMClientError(f"Unexpected LLM generation error: {exc}") from exc
            return None

    def generate_current_weather_summary(
        self,
        city: str,
        weather_data: Dict[str, Any],
        raise_on_error: bool = False,
    ) -> Optional[str]:
        """Generate a concise, professional meteorological narrative from current weather observations.

        Args:
            city: Target city name.
            weather_data: Dictionary of live weather metrics.
            raise_on_error: If True, re-raises LLMClientError instead of returning None.

        Returns:
            Clean professional meteorological summary string if successful, or None on failure.
        """
        if not weather_data:
            logger.warning("Empty weather data provided for current weather summary; skipping.")
            return None

        payload = format_current_weather_payload(
            city=city,
            weather_data=weather_data,
        )

        try:
            raw_summary = self.client.generate_completion(
                system_prompt=CURRENT_WEATHER_SUMMARY_SYSTEM_PROMPT,
                user_content=payload,
            )

            cleaned = self._clean_llm_output(raw_summary)
            if not cleaned:
                logger.warning("Sanitized current weather LLM output is empty.")
                return None

            return cleaned

        except LLMClientError as exc:
            logger.warning("LLM generation failed for current weather summary city='%s': %s", city, exc)
            if raise_on_error:
                raise
            return None
        except Exception as exc:
            logger.exception("Unexpected error during current weather LLM generation for city='%s': %s", city, exc)
            if raise_on_error:
                raise LLMClientError(f"Unexpected LLM generation error: {exc}") from exc
            return None

    @staticmethod
    def _clean_llm_output(text: str) -> str:
        """Strip surrounding formatting or accidental markdown artifacts from output."""
        if not text:
            return ""

        cleaned = text.strip()

        # Remove surrounding markdown code fences if model returned ``` ... ```
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = re.sub(r"^```(?:markdown|text)?\n?", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        # Strip surrounding double or single quotes if model wrapped response in quotes
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        return cleaned
