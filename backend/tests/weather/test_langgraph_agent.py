"""Unit and integration tests for the LangGraph Weather Agent workflow."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.agents.weather_agent_graph import (
    create_weather_agent_graph,
    run_weather_agent,
)
from app.agents.weather_agent_nodes import (
    analyze_query_node,
    current_weather_node,
    forecast_node,
    general_weather_node,
    generate_response_node,
    historical_average_node,
    parse_query_heuristics,
    route_by_intent,
    FRIENDLY_HELP_MESSAGE,
)
from app.agents.weather_agent_state import WeatherAgentState
from app.clients.groq_client import LLMClientError, LLMTimeoutError
from app.clients.weather_client import CityNotFoundError, WeatherClientError, WeatherTimeoutError
from app.main import app
from app.schemas.weather_schema import (
    ForecastDay,
    ForecastResponse,
    WeatherResponse,
    WeatherStatisticsResponse,
)


@pytest.fixture
def mock_groq_client():
    """Mock Groq client fixture."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_weather_response():
    """Mock canonical WeatherResponse."""
    return WeatherResponse(
        city="Indore",
        temperature=31.5,
        feels_like=30.2,
        humidity=27,
        wind_speed=8.8,
        condition="Clear",
        observed_at="2026-10-03T12:00:00Z",
        resolved_address="Indore, Madhya Pradesh, India",
    )


@pytest.fixture
def mock_forecast_response():
    """Mock canonical ForecastResponse."""
    days = [
        ForecastDay(
            date=f"2026-10-0{i}",
            temperature_min=22.0 + i,
            temperature_max=32.0 + i,
            condition="Sunny",
            precipitation_probability=10,
            humidity=50,
            wind_speed=12.0,
        )
        for i in range(1, 6)
    ]
    return ForecastResponse(
        city="Mumbai",
        forecast=days,
        resolved_address="Mumbai, Maharashtra, India",
    )


@pytest.fixture
def mock_statistics_response():
    """Mock canonical WeatherStatisticsResponse."""
    return WeatherStatisticsResponse(
        city="Indore",
        provider="Open-Meteo",
        period_type="week",
        duration=2,
        period_value=2,
        start_date="2026-09-19",
        end_date="2026-10-03",
        overall_average_temperature_celsius=27.4,
        average_temperature_celsius=27.4,
        total_observation_days=14,
        observation_days=14,
        data_coverage_percentage=100.0,
        coverage_percentage=100.0,
        status="SUCCESS",
        period="week",
        average_temperature=27.4,
    )


# ==============================================================================
# 1. Query Analysis & Heuristic Tests
# ==============================================================================
class TestQueryAnalysis:
    """Test suite for intent classification and parameter extraction."""

    def test_empty_query(self):
        state: WeatherAgentState = {"query": "   "}
        res = analyze_query_node(state)
        assert res["intent"] == "GENERAL_WEATHER_QUERY"
        assert res["error"] == "empty_query"
        assert res["city"] is None

    def test_heuristics_all_six_user_queries(self):
        # 1. Indore current weather
        q1 = parse_query_heuristics("What is the weather in Indore?")
        assert q1["intent"] == "CURRENT_WEATHER"
        assert q1["city"] == "Indore"

        # 2. Bhopal current temperature
        q2 = parse_query_heuristics("What's the current temperature in Bhopal?")
        assert q2["intent"] == "CURRENT_WEATHER"
        assert q2["city"] == "Bhopal"

        # 3. Mumbai 5-day forecast
        q3 = parse_query_heuristics("Give me the 5-day forecast for Mumbai.")
        assert q3["intent"] == "FORECAST"
        assert q3["city"] == "Mumbai"
        assert q3["parameters"]["days"] == 5

        # 4. Indore last 2 weeks average
        q4 = parse_query_heuristics("What was the average temperature in Indore for the last 2 weeks?")
        assert q4["intent"] == "HISTORICAL_AVERAGE"
        assert q4["city"] == "Indore"
        assert q4["parameters"]["period"] == "week"
        assert q4["parameters"]["duration"] == 2

        # 5. Last 3 months average (no city)
        q5 = parse_query_heuristics("Show me the average temperature for the last 3 months.")
        assert q5["intent"] == "HISTORICAL_AVERAGE"
        assert q5["city"] is None
        assert q5["parameters"]["period"] == "month"
        assert q5["parameters"]["duration"] == 3

        # 6. Delhi weather
        q6 = parse_query_heuristics("Tell me the weather in Delhi.")
        assert q6["intent"] == "CURRENT_WEATHER"
        assert q6["city"] == "Delhi"

    def test_analyze_query_node_groq_success(self, mock_groq_client):
        mock_groq_client.generate_completion.return_value = (
            '{"city": "Indore", "intent": "CURRENT_WEATHER", "parameters": {}}'
        )
        state: WeatherAgentState = {"query": "What is the weather in Indore?"}
        res = analyze_query_node(state, client=mock_groq_client)
        assert res["intent"] == "CURRENT_WEATHER"
        assert res["city"] == "Indore"
        assert res["error"] is None

    def test_analyze_query_node_groq_failure_fallback(self, mock_groq_client):
        mock_groq_client.generate_completion.side_effect = LLMTimeoutError("Request timed out")
        state: WeatherAgentState = {"query": "Give me the 5-day forecast for Mumbai."}
        res = analyze_query_node(state, client=mock_groq_client)
        assert res["intent"] == "FORECAST"
        assert res["city"] == "Mumbai"
        assert res["parameters"]["days"] == 5


# ==============================================================================
# 2. Router Tests
# ==============================================================================
class TestConditionalRouter:
    """Test suite for intent-based routing function."""

    def test_routing_paths(self):
        assert route_by_intent({"intent": "CURRENT_WEATHER"}) == "current_weather"
        assert route_by_intent({"intent": "FORECAST"}) == "forecast"
        assert route_by_intent({"intent": "HISTORICAL_AVERAGE"}) == "historical_average"
        assert route_by_intent({"intent": "GENERAL_WEATHER_QUERY"}) == "general_weather"
        assert route_by_intent({"intent": "UNKNOWN"}) == "general_weather"


# ==============================================================================
# 3. Tool & Handler Nodes Tests
# ==============================================================================
class TestWeatherNodes:
    """Test suite for tool execution nodes."""

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_current_weather_node_success(self, mock_get_current, mock_weather_response):
        mock_get_current.return_value = mock_weather_response
        state: WeatherAgentState = {"city": "Indore"}
        res = current_weather_node(state)
        assert res["error"] is None
        assert res["weather_data"]["city"] == "Indore"
        assert res["weather_data"]["temperature"] == 31.5

    def test_current_weather_node_missing_city(self):
        state: WeatherAgentState = {"city": None}
        res = current_weather_node(state)
        assert res["error"] == "missing_city"

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_current_weather_node_city_not_found(self, mock_get_current):
        mock_get_current.side_effect = CityNotFoundError("City not found: Atlantis")
        state: WeatherAgentState = {"city": "Atlantis"}
        res = current_weather_node(state)
        assert res["error"] == "city_not_found"

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_current_weather_node_service_failure(self, mock_get_current):
        mock_get_current.side_effect = WeatherTimeoutError("Timeout")
        state: WeatherAgentState = {"city": "Indore"}
        res = current_weather_node(state)
        assert res["error"] == "weather_service_error"

    @patch("app.agents.weather_agent_nodes.get_weather_forecast")
    def test_forecast_node_success(self, mock_get_forecast, mock_forecast_response):
        mock_get_forecast.return_value = mock_forecast_response
        state: WeatherAgentState = {"city": "Mumbai", "parameters": {"days": 5}}
        res = forecast_node(state)
        assert res["error"] is None
        assert res["weather_data"]["city"] == "Mumbai"
        assert len(res["weather_data"]["forecast"]) == 5

    @patch("app.agents.weather_agent_nodes.get_historical_average_weather")
    def test_historical_average_node_success(self, mock_get_hist, mock_statistics_response):
        mock_get_hist.return_value = mock_statistics_response
        state: WeatherAgentState = {"city": "Indore", "parameters": {"period": "week", "duration": 2}}
        res = historical_average_node(state)
        assert res["error"] is None
        assert res["weather_data"]["city"] == "Indore"
        assert res["weather_data"]["duration"] == 2

    def test_general_weather_node(self):
        state: WeatherAgentState = {"query": "Tell me a joke"}
        res = general_weather_node(state)
        assert res["error"] == "unsupported_query"


# ==============================================================================
# 4. Response Generation & Fallback Tests
# ==============================================================================
class TestResponseGenerationNode:
    """Test suite for meteorological response generation and error handling."""

    def test_generate_response_missing_city(self):
        state: WeatherAgentState = {"error": "missing_city"}
        res = generate_response_node(state)
        assert "Please specify a city" in res["response"]

    def test_generate_response_city_not_found(self):
        state: WeatherAgentState = {"error": "city_not_found", "city": "Atlantis"}
        res = generate_response_node(state)
        assert "could not find weather information for 'Atlantis'" in res["response"]

    def test_generate_response_weather_service_error(self):
        state: WeatherAgentState = {"error": "weather_service_error"}
        res = generate_response_node(state)
        assert "Weather data is currently unavailable" in res["response"]

    def test_generate_response_empty_query(self):
        state: WeatherAgentState = {"error": "empty_query"}
        res = generate_response_node(state)
        assert res["response"] == FRIENDLY_HELP_MESSAGE

    def test_generate_response_unsupported_query(self):
        state: WeatherAgentState = {"error": "unsupported_query"}
        res = generate_response_node(state)
        assert res["response"] == FRIENDLY_HELP_MESSAGE

    def test_generate_response_groq_success(self, mock_groq_client, mock_weather_response):
        mock_groq_client.generate_completion.return_value = "Indore is experiencing clear weather with 31.5°C."
        state: WeatherAgentState = {
            "intent": "CURRENT_WEATHER",
            "city": "Indore",
            "weather_data": mock_weather_response.model_dump(),
        }
        res = generate_response_node(state, client=mock_groq_client)
        assert res["response"] == "Indore is experiencing clear weather with 31.5°C."

    def test_generate_response_groq_failure_deterministic_fallback(self, mock_groq_client, mock_weather_response):
        mock_groq_client.generate_completion.side_effect = LLMClientError("Provider offline")
        state: WeatherAgentState = {
            "intent": "CURRENT_WEATHER",
            "city": "Indore",
            "weather_data": mock_weather_response.model_dump(),
        }
        res = generate_response_node(state, client=mock_groq_client)
        assert "Indore" in res["response"]
        assert "31.5" in res["response"]
        assert "Clear" in res["response"]


# ==============================================================================
# 5. Full LangGraph End-to-End Workflow Tests
# ==============================================================================
class TestLangGraphEndToEnd:
    """End-to-end integration tests for the LangGraph StateGraph."""

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_query_1_indore_current_weather(self, mock_weather, mock_weather_response):
        mock_weather.return_value = mock_weather_response
        state = run_weather_agent("What is the weather in Indore?")
        assert state["intent"] == "CURRENT_WEATHER"
        assert state["city"] == "Indore"
        assert state["error"] is None
        assert state["weather_data"] is not None
        assert "Indore" in state["response"]

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_query_2_bhopal_current_temperature(self, mock_weather):
        mock_weather.return_value = WeatherResponse(
            city="Bhopal",
            temperature=30.0,
            feels_like=29.0,
            humidity=35,
            wind_speed=10.0,
            condition="Sunny",
            observed_at="2026-10-03T12:00:00Z",
            resolved_address="Bhopal, Madhya Pradesh, India",
        )
        state = run_weather_agent("What's the current temperature in Bhopal?")
        assert state["intent"] == "CURRENT_WEATHER"
        assert state["city"] == "Bhopal"
        assert state["error"] is None
        assert "Bhopal" in state["response"]

    @patch("app.agents.weather_agent_nodes.get_weather_forecast")
    def test_query_3_mumbai_forecast(self, mock_forecast, mock_forecast_response):
        mock_forecast.return_value = mock_forecast_response
        state = run_weather_agent("Give me the 5-day forecast for Mumbai.")
        assert state["intent"] == "FORECAST"
        assert state["city"] == "Mumbai"
        assert state["parameters"].get("days") == 5
        assert state["error"] is None
        assert "Mumbai" in state["response"]

    @patch("app.agents.weather_agent_nodes.get_historical_average_weather")
    def test_query_4_indore_last_2_weeks(self, mock_hist, mock_statistics_response):
        mock_hist.return_value = mock_statistics_response
        state = run_weather_agent("What was the average temperature in Indore for the last 2 weeks?")
        assert state["intent"] == "HISTORICAL_AVERAGE"
        assert state["city"] == "Indore"
        assert state["parameters"].get("period") == "week"
        assert state["parameters"].get("duration") == 2
        assert state["error"] is None
        assert "Indore" in state["response"]

    def test_query_5_last_3_months_missing_city(self):
        state = run_weather_agent("Show me the average temperature for the last 3 months.")
        assert state["intent"] == "HISTORICAL_AVERAGE"
        assert state["city"] is None
        assert state["error"] == "missing_city"
        assert "Please specify a city" in state["response"]

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_query_6_delhi_weather(self, mock_weather):
        mock_weather.return_value = WeatherResponse(
            city="Delhi",
            temperature=33.0,
            feels_like=34.0,
            humidity=40,
            wind_speed=7.5,
            condition="Haze",
            observed_at="2026-10-03T12:00:00Z",
            resolved_address="Delhi, India",
        )
        state = run_weather_agent("Tell me the weather in Delhi.")
        assert state["intent"] == "CURRENT_WEATHER"
        assert state["city"] == "Delhi"
        assert state["error"] is None
        assert "Delhi" in state["response"]

    def test_edge_case_unknown_city(self):
        state = run_weather_agent("What is the weather in NonExistentCity99xyz?")
        assert state["error"] == "city_not_found"
        assert "NonExistentCity99Xyz" in state["response"] or "could not find weather information" in state["response"]

    def test_edge_case_empty_query(self):
        state = run_weather_agent("   ")
        assert state["error"] == "empty_query"
        assert state["response"] == FRIENDLY_HELP_MESSAGE

    def test_edge_case_unsupported_query(self):
        state = run_weather_agent("Can you write a poem about artificial intelligence?")
        assert state["intent"] == "GENERAL_WEATHER_QUERY"
        assert state["response"] == FRIENDLY_HELP_MESSAGE


# ==============================================================================
# 6. FastAPI Router Tests (/api/v1/agent/query)
# ==============================================================================
class TestAgentRouterEndpoints:
    """Test suite for FastAPI agent router endpoints."""

    def setup_method(self):
        self.client = TestClient(app)

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_post_agent_query_endpoint(self, mock_weather, mock_weather_response):
        mock_weather.return_value = mock_weather_response
        resp = self.client.post("/api/v1/agent/query", json={"query": "What is the weather in Indore?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "What is the weather in Indore?"
        assert data["city"] == "Indore"
        assert data["intent"] == "CURRENT_WEATHER"
        assert "Indore" in data["response"]

    @patch("app.agents.weather_agent_nodes.get_current_weather")
    def test_get_agent_query_endpoint(self, mock_weather, mock_weather_response):
        mock_weather.return_value = mock_weather_response
        resp = self.client.get("/api/v1/agent/query", params={"q": "What is the weather in Indore?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["city"] == "Indore"
        assert data["intent"] == "CURRENT_WEATHER"
        assert "Indore" in data["response"]
