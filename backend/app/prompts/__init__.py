"""Prompts layer: System prompt templates and LLM instruction sets.

Architecture Rule:
- Prompts encapsulate instructions, safety rules, and templating.
"""

from app.prompts.weather_prompts import (
    WEATHER_SUMMARY_SYSTEM_PROMPT,
    format_weather_summary_payload,
)

__all__ = [
    "WEATHER_SUMMARY_SYSTEM_PROMPT",
    "format_weather_summary_payload",
]
