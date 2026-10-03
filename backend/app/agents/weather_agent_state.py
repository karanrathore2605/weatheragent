"""State definition for the LangGraph Weather Agent workflow."""

from typing import Any, Dict, Optional, TypedDict


class WeatherAgentState(TypedDict, total=False):
    """Shared state dictionary tracked across all LangGraph nodes in the weather workflow.

    Fields:
        query: The raw natural language input query from the user.
        city: Extracted city name (e.g., 'Indore', 'Bhopal', 'Mumbai').
        intent: Classified user intent:
            - 'CURRENT_WEATHER'
            - 'FORECAST'
            - 'HISTORICAL_AVERAGE'
            - 'GENERAL_WEATHER_QUERY'
        parameters: Additional parsed parameters (e.g. days=5, period='week', duration=2).
        weather_data: Raw domain dictionary returned by weather tools/services.
        result: Canonical structured result representation.
        response: Final professional meteorological response or friendly guidance.
        error: Standardized error code or message if validation or API failure occurred.
    """

    query: str
    city: Optional[str]
    intent: Optional[str]
    parameters: Optional[Dict[str, Any]]
    weather_data: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    response: Optional[str]
    error: Optional[str]
