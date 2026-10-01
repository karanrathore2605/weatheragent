"""Tools layer: Encapsulates agent-callable functions and schema definitions.

Architecture Rule:
- Future branch: LangChain/LangGraph tools for weather lookups, calculators, email dispatch.
- Agent -> Tool -> Service.
"""

from app.tools.weather_tools import get_current_weather

__all__ = ["get_current_weather"]
