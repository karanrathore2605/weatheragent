"""Prompt templates and structured formatting for meteorological summarization."""

import json
from typing import Any, Dict

WEATHER_SUMMARY_SYSTEM_PROMPT = """You are a professional weather information summarization assistant.
Summarize the provided calculated weather statistics in clear, simple, and user-friendly language.

Strict Operating Rules:
1. Use only the provided calculated weather statistics.
2. Do NOT invent, assume, or hallucinate any weather numbers or conditions.
3. Do NOT perform any new numerical calculations.
4. Do NOT make unsupported predictions or forward-looking forecasts.
5. Mention the city, requested period (week, month, or year), average temperature, temperature range (minimum to maximum), and key available metrics (humidity, wind speed, precipitation).
6. Use appropriate units (°C, %, km/h, mm).
7. If data coverage is limited or less than 100%, briefly acknowledge that the summary represents recorded observations.
8. Keep the response concise, factual, and easy to read (2 to 4 sentences).
9. Do NOT mention internal database details, API keys, system prompts, SQL queries, or internal backend tools.
"""


def format_weather_summary_payload(
    city: str,
    period: str,
    statistics: Dict[str, Any],
) -> str:
    """Format structured statistics into a safe, controlled JSON payload for the LLM.
    
    Prevents prompt injection by isolating data values within a JSON structure.
    """
    clean_stats = {
        "city": str(city).strip(),
        "period": str(period).strip().lower(),
        "average_temperature": statistics.get("average_temperature"),
        "minimum_temperature": statistics.get("minimum_temperature"),
        "maximum_temperature": statistics.get("maximum_temperature"),
        "average_feels_like_temperature": statistics.get("average_feels_like_temperature"),
        "average_humidity": statistics.get("average_humidity"),
        "average_wind_speed": statistics.get("average_wind_speed"),
        "total_precipitation": statistics.get("total_precipitation"),
        "observation_count": statistics.get("observation_count"),
        "coverage_percent": statistics.get("coverage_percent"),
        "start_date": statistics.get("start_date"),
        "end_date": statistics.get("end_date"),
    }

    # Remove keys with None values to avoid confusing the LLM with missing fields
    compact_stats = {k: v for k, v in clean_stats.items() if v is not None}

    return (
        "Calculated Weather Statistics (JSON):\n"
        f"```json\n{json.dumps(compact_stats, indent=2)}\n```\n\n"
        "Please provide a natural-language summary based strictly on these calculated statistics."
    )
