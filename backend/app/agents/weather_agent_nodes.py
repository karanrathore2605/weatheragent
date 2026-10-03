"""Node definitions and conditional routing for the LangGraph Weather Agent workflow."""

import json
import re
from typing import Any, Dict, Optional

from app.agents.weather_agent_prompts import (
    AGENT_RESPONSE_SYSTEM_PROMPT,
    INTENT_ANALYSIS_SYSTEM_PROMPT,
    format_agent_response_payload,
    format_query_analysis_payload,
)
from app.agents.weather_agent_state import WeatherAgentState
from app.clients.groq_client import BaseLLMClient, GroqClient, LLMClientError
from app.clients.weather_client import (
    AmbiguousLocationError,
    CityNotFoundError,
    WeatherClientError,
)
from app.tools.weather_tools import (
    get_current_weather,
    get_historical_average_weather,
    get_weather_forecast,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Standard friendly error message for unsupported queries or empty input
FRIENDLY_HELP_MESSAGE = (
    "I can help with current weather, forecasts, and historical temperature analysis. "
    "Please provide a city and tell me what weather information you need."
)

STOP_WORDS = {
    "the", "a", "an", "last", "past", "next", "this", "today", "tomorrow",
    "yesterday", "week", "weeks", "month", "months", "year", "years", "day", "days"
}


# ==============================================================================
# Helper: Rule-based Heuristic / Fallback Query Parser
# ==============================================================================
def parse_query_heuristics(query: str) -> Dict[str, Any]:
    """Parse user query deterministically using regex and keyword heuristics.

    Used when LLM is unavailable, times out, or returns non-JSON output.
    """
    clean_q = query.strip()
    q_lower = clean_q.lower()

    # 1. City extraction
    city: Optional[str] = None

    # Try pattern: "in <City>", "for <City>", "of <City>"
    match_city = re.search(r"\b(?:in|for|at|of)\s+([A-Za-z]+)", clean_q)
    if match_city:
        candidate = match_city.group(1).strip()
        if candidate.lower() not in STOP_WORDS and len(candidate) >= 2:
            city = candidate.title()

    # 2. Intent extraction
    intent = "GENERAL_WEATHER_QUERY"
    parameters: Dict[str, Any] = {}

    is_forecast = bool(
        re.search(r"\b(?:forecast|future|next\s+\d+\s+days?|upcoming)\b", q_lower)
    )
    is_historical = bool(
        re.search(r"\b(?:average|historical|history|last\s+\d+|past\s+\d+)\b", q_lower)
    )
    is_current = bool(
        re.search(r"\b(?:current|temperature|today|now|weather|conditions?)\b", q_lower)
    )

    if is_forecast:
        intent = "FORECAST"
        day_match = re.search(r"(\d+)\s*(?:-| )?day", q_lower)
        days = int(day_match.group(1)) if day_match else 5
        parameters["days"] = max(1, min(10, days))

    elif is_historical:
        intent = "HISTORICAL_AVERAGE"
        if "month" in q_lower:
            parameters["period"] = "month"
            m_match = re.search(r"(\d+)\s*month", q_lower)
            parameters["duration"] = int(m_match.group(1)) if m_match else 1
        elif "week" in q_lower:
            parameters["period"] = "week"
            w_match = re.search(r"(\d+)\s*week", q_lower)
            parameters["duration"] = int(w_match.group(1)) if w_match else 1
        else:
            parameters["period"] = "week"
            parameters["duration"] = 1

    elif is_current:
        intent = "CURRENT_WEATHER"

    return {
        "city": city,
        "intent": intent,
        "parameters": parameters,
    }


# ==============================================================================
# Node 1: Analyze Query Node
# ==============================================================================
def analyze_query_node(
    state: WeatherAgentState,
    client: Optional[BaseLLMClient] = None,
) -> WeatherAgentState:
    """Analyze natural-language user query to extract city, intent, and parameters."""
    query = state.get("query", "")
    if not query or not query.strip():
        logger.info("Empty query received in analyze_query_node")
        return {
            **state,
            "city": None,
            "intent": "GENERAL_WEATHER_QUERY",
            "parameters": {},
            "error": "empty_query",
        }

    raw_query = query.strip()
    groq_client = client or GroqClient()

    parsed_result: Optional[Dict[str, Any]] = None

    try:
        raw_completion = groq_client.generate_completion(
            system_prompt=INTENT_ANALYSIS_SYSTEM_PROMPT,
            user_content=format_query_analysis_payload(raw_query),
            temperature=0.0,
            max_tokens=1024,
        )

        cleaned_text = raw_completion.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```(?:json)?\n?", "", cleaned_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r"\n?```$", "", cleaned_text)
            cleaned_text = cleaned_text.strip()

        data = json.loads(cleaned_text)
        if isinstance(data, dict) and "intent" in data:
            parsed_result = data
            logger.info("Groq query analysis successful: intent=%s, city=%s", data.get("intent"), data.get("city"))
    except (LLMClientError, json.JSONDecodeError, Exception) as exc:
        logger.warning("Groq query analysis failed or skipped (%s). Falling back to rule heuristics.", exc)

    if not parsed_result:
        parsed_result = parse_query_heuristics(raw_query)
        logger.info("Heuristic query analysis: intent=%s, city=%s", parsed_result.get("intent"), parsed_result.get("city"))

    extracted_city = parsed_result.get("city")
    if extracted_city and isinstance(extracted_city, str):
        extracted_city = extracted_city.strip().title()
        if extracted_city.lower() in STOP_WORDS or len(extracted_city) < 2:
            extracted_city = None
    else:
        extracted_city = None

    extracted_intent = parsed_result.get("intent", "GENERAL_WEATHER_QUERY")
    valid_intents = {"CURRENT_WEATHER", "FORECAST", "HISTORICAL_AVERAGE", "GENERAL_WEATHER_QUERY"}
    if extracted_intent not in valid_intents:
        extracted_intent = "GENERAL_WEATHER_QUERY"

    extracted_parameters = parsed_result.get("parameters") or {}

    return {
        **state,
        "city": extracted_city,
        "intent": extracted_intent,
        "parameters": extracted_parameters,
        "error": None,
    }


# ==============================================================================
# Conditional Router Function
# ==============================================================================
def route_by_intent(state: WeatherAgentState) -> str:
    """Evaluate classified intent and return the corresponding LangGraph node name."""
    intent = state.get("intent")
    if intent == "CURRENT_WEATHER":
        return "current_weather"
    elif intent == "FORECAST":
        return "forecast"
    elif intent == "HISTORICAL_AVERAGE":
        return "historical_average"
    else:
        return "general_weather"


# ==============================================================================
# Node 2: Current Weather Node
# ==============================================================================
def current_weather_node(
    state: WeatherAgentState,
    service: Optional[Any] = None,
) -> WeatherAgentState:
    """Fetch current weather data using the weather tools layer."""
    city = state.get("city")
    if not city:
        logger.info("Current weather requested without city parameter")
        return {**state, "error": "missing_city", "weather_data": None, "result": None}

    try:
        response = get_current_weather(city=city, service=service)
        data = response.model_dump()
        return {
            **state,
            "weather_data": data,
            "result": data,
            "error": None,
        }
    except AmbiguousLocationError as exc:
        logger.warning("Ambiguous location in current_weather_node: %s", exc)
        return {**state, "error": str(exc), "weather_data": None, "result": None}
    except CityNotFoundError:
        logger.warning("City not found: %s", city)
        return {**state, "error": "city_not_found", "weather_data": None, "result": None}
    except (ValueError, WeatherClientError) as exc:
        logger.warning("Weather client error fetching current weather for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}
    except Exception as exc:
        logger.exception("Unexpected error in current_weather_node for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}


# ==============================================================================
# Node 3: Forecast Node
# ==============================================================================
def forecast_node(
    state: WeatherAgentState,
    service: Optional[Any] = None,
) -> WeatherAgentState:
    """Fetch multi-day weather forecast using the weather tools layer."""
    city = state.get("city")
    if not city:
        logger.info("Forecast requested without city parameter")
        return {**state, "error": "missing_city", "weather_data": None, "result": None}

    params = state.get("parameters") or {}
    days = params.get("days", 5)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 5
    days = max(1, min(10, days))

    try:
        response = get_weather_forecast(city=city, days=days, service=service)
        data = response.model_dump()
        return {
            **state,
            "weather_data": data,
            "result": data,
            "error": None,
        }
    except AmbiguousLocationError as exc:
        logger.warning("Ambiguous location for forecast '%s': %s", city, exc)
        return {**state, "error": str(exc), "weather_data": None, "result": None}
    except CityNotFoundError:
        logger.warning("City not found for forecast: %s", city)
        return {**state, "error": "city_not_found", "weather_data": None, "result": None}
    except (ValueError, WeatherClientError) as exc:
        logger.warning("Weather client error fetching forecast for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}
    except Exception as exc:
        logger.exception("Unexpected error in forecast_node for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}


# ==============================================================================
# Node 4: Historical Average Node
# ==============================================================================
def historical_average_node(
    state: WeatherAgentState,
    service: Optional[Any] = None,
) -> WeatherAgentState:
    """Fetch historical temperature averages using the weather tools layer."""
    city = state.get("city")
    if not city:
        logger.info("Historical average requested without city parameter")
        return {**state, "error": "missing_city", "weather_data": None, "result": None}

    params = state.get("parameters") or {}
    period = params.get("period", "week")
    if period not in ("week", "month"):
        period = "week"

    duration = params.get("duration", 1)
    try:
        duration = int(duration)
    except (ValueError, TypeError):
        duration = 1

    if period == "week":
        duration = max(1, min(3, duration))
    else:
        duration = max(1, min(12, duration))

    try:
        response = get_historical_average_weather(
            city=city,
            period=period,
            duration=duration,
            service=service,
        )
        data = response.model_dump()
        return {
            **state,
            "weather_data": data,
            "result": data,
            "error": None,
        }
    except AmbiguousLocationError as exc:
        logger.warning("Ambiguous location for historical statistics '%s': %s", city, exc)
        return {**state, "error": str(exc), "weather_data": None, "result": None}
    except CityNotFoundError:
        logger.warning("City not found for historical statistics: %s", city)
        return {**state, "error": "city_not_found", "weather_data": None, "result": None}
    except (ValueError, WeatherClientError) as exc:
        logger.warning("Client error fetching historical statistics for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}
    except Exception as exc:
        logger.exception("Unexpected error in historical_average_node for '%s': %s", city, exc)
        return {**state, "error": "weather_service_error", "weather_data": None, "result": None}


# ==============================================================================
# Node 5: General Weather Node
# ==============================================================================
def general_weather_node(state: WeatherAgentState) -> WeatherAgentState:
    """Handle unsupported or general queries."""
    current_error = state.get("error")
    if not current_error:
        return {
            **state,
            "error": "unsupported_query",
            "weather_data": None,
            "result": None,
        }
    return state


import unicodedata

def _sanitize_text(text: str) -> str:
    """Normalize unicode punctuation, dashes, spaces, and quotes to standard representations."""
    if not text:
        return ""
    replacements = {
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u202f": " ",
        "\xa0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u207b": "-",
        "\u00b9": "1",
        "\u00b2": "2",
        "\u00b3": "3",
        "\u2212": "-",
        "\u00b0": "°",
    }
    cleaned = text
    for char, repl in replacements.items():
        cleaned = cleaned.replace(char, repl)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    return cleaned


# ==============================================================================
# Node 6: Generate Response Node
# ==============================================================================
def generate_response_node(
    state: WeatherAgentState,
    client: Optional[BaseLLMClient] = None,
) -> WeatherAgentState:
    """Synthesize final professional meteorological response using Groq LLM or safe fallback."""
    error = state.get("error")
    city = state.get("city")
    intent = state.get("intent", "GENERAL_WEATHER_QUERY")
    weather_data = state.get("weather_data")

    # Handle error or missing city cases
    if error and ("Multiple locations match" in str(error) or "specify the country" in str(error)):
        return {**state, "response": str(error)}

    if error == "missing_city":
        response_text = (
            "Please specify a city to get weather information. "
            "For example: 'What is the weather in Indore?' or 'Show me the 5-day forecast for Mumbai.'"
        )
        return {**state, "response": response_text}

    if error == "city_not_found":
        target = f"'{city}'" if city else "the specified location"
        response_text = f"I could not find weather information for {target}. Please check the city name and try again."
        return {**state, "response": response_text}

    if error == "weather_service_error":
        response_text = "Weather data is currently unavailable. Please try again shortly."
        return {**state, "response": response_text}

    if error in ("empty_query", "unsupported_query") or not weather_data:
        return {**state, "response": FRIENDLY_HELP_MESSAGE}

    # Weather data is available -> Attempt Groq synthesis
    groq_client = client or GroqClient()
    try:
        payload = format_agent_response_payload(
            intent=intent,
            city=city,
            weather_data=weather_data,
        )
        raw_response = groq_client.generate_completion(
            system_prompt=AGENT_RESPONSE_SYSTEM_PROMPT,
            user_content=payload,
            temperature=0.2,
            max_tokens=1024,
        )

        cleaned = raw_response.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = re.sub(r"^```(?:markdown|text)?\n?", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        cleaned = _sanitize_text(cleaned)
        if cleaned:
            return {**state, "response": cleaned}

    except Exception as exc:
        logger.warning("Groq response generation failed (%s). Generating deterministic response.", exc)

    # Deterministic factual fallback (strictly non-hallucinatory)
    fallback_response = _build_deterministic_response(intent=intent, city=city, data=weather_data)
    fallback_response = _sanitize_text(fallback_response)
    return {**state, "response": fallback_response}


def _build_deterministic_response(intent: str, city: Optional[str], data: Dict[str, Any]) -> str:
    """Build a deterministic factual response from data without calling LLM."""
    resolved_city = data.get("city") or city or "The requested location"

    if intent == "CURRENT_WEATHER":
        temp = data.get("temperature", "N/A")
        feels = data.get("feels_like", "N/A")
        cond = data.get("condition", "Clear")
        hum = data.get("humidity", "N/A")
        wind = data.get("wind_speed", "N/A")
        return (
            f"{resolved_city} is currently experiencing {cond} conditions with a temperature of {temp}°C "
            f"(feels like {feels}°C), humidity at {hum}%, and winds around {wind} km/h."
        )

    elif intent == "FORECAST":
        forecast_days = data.get("forecast") or []
        count = len(forecast_days)
        if forecast_days:
            min_temps = [d.get("temperature_min", 0.0) for d in forecast_days]
            max_temps = [d.get("temperature_max", 0.0) for d in forecast_days]
            conditions = {d.get("condition", "Clear") for d in forecast_days}
            cond_str = ", ".join(sorted(conditions))
            return (
                f"The {count}-day forecast for {resolved_city} indicates temperatures ranging from "
                f"{min(min_temps)}°C to {max(max_temps)}°C with predominant conditions of {cond_str}."
            )
        return f"Weather forecast for {resolved_city} is currently available for {count} days."

    elif intent == "HISTORICAL_AVERAGE":
        avg_temp = (
            data.get("overall_average_temperature_celsius")
            or data.get("average_temperature_celsius")
            or data.get("statistics", {}).get("average_temperature")
        )
        duration = data.get("duration", 1)
        period = data.get("period_type", "week")
        period_str = f"{duration} {period}s" if duration > 1 else f"1 {period}"
        obs_days = data.get("total_observation_days") or data.get("observation_days") or "several"
        return (
            f"The average temperature in {resolved_city} over the past {period_str} was {avg_temp}°C "
            f"across {obs_days} observation days."
        )

    return f"Weather information for {resolved_city} has been successfully retrieved."
