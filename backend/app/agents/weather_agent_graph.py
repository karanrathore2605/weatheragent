"""LangGraph StateGraph assembly for the Weather Agent."""

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.weather_agent_nodes import (
    analyze_query_node,
    current_weather_node,
    forecast_node,
    general_weather_node,
    generate_response_node,
    historical_average_node,
    route_by_intent,
)
from app.agents.weather_agent_state import WeatherAgentState
from app.clients.groq_client import BaseLLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_weather_agent_graph(
    llm_client: Optional[BaseLLMClient] = None,
    weather_service: Optional[Any] = None,
    statistics_service: Optional[Any] = None,
) -> Any:
    """Construct and compile the LangGraph workflow for the weather agent.

    Graph Architecture:
    START
      ↓
    analyze_query
      ↓
    conditional_router (route_by_intent)
      ├── current_weather
      ├── forecast
      ├── historical_average
      └── general_weather
            ↓
    generate_response
            ↓
    END
    """
    workflow = StateGraph(WeatherAgentState)

    # Wrap nodes to allow dependency injection for testing and extensibility
    def _analyze_node(state: WeatherAgentState) -> WeatherAgentState:
        return analyze_query_node(state, client=llm_client)

    def _current_weather(state: WeatherAgentState) -> WeatherAgentState:
        return current_weather_node(state, service=weather_service)

    def _forecast(state: WeatherAgentState) -> WeatherAgentState:
        return forecast_node(state, service=weather_service)

    def _historical(state: WeatherAgentState) -> WeatherAgentState:
        return historical_average_node(state, service=statistics_service)

    def _response_node(state: WeatherAgentState) -> WeatherAgentState:
        return generate_response_node(state, client=llm_client)

    # 1. Register nodes
    workflow.add_node("analyze_query", _analyze_node)
    workflow.add_node("current_weather", _current_weather)
    workflow.add_node("forecast", _forecast)
    workflow.add_node("historical_average", _historical)
    workflow.add_node("general_weather", general_weather_node)
    workflow.add_node("generate_response", _response_node)

    # 2. Add entry edge
    workflow.add_edge(START, "analyze_query")

    # 3. Add conditional routing edges
    workflow.add_conditional_edges(
        "analyze_query",
        route_by_intent,
        {
            "current_weather": "current_weather",
            "forecast": "forecast",
            "historical_average": "historical_average",
            "general_weather": "general_weather",
        },
    )

    # 4. Connect tool and handler nodes to generate_response
    workflow.add_edge("current_weather", "generate_response")
    workflow.add_edge("forecast", "generate_response")
    workflow.add_edge("historical_average", "generate_response")
    workflow.add_edge("general_weather", "generate_response")

    # 5. Connect response node to END
    workflow.add_edge("generate_response", END)

    logger.info("LangGraph weather agent workflow compiled successfully")
    return workflow.compile()


# Default singleton instance
default_weather_agent_graph = create_weather_agent_graph()


def run_weather_agent(
    query: str,
    llm_client: Optional[BaseLLMClient] = None,
    weather_service: Optional[Any] = None,
    statistics_service: Optional[Any] = None,
) -> WeatherAgentState:
    """Execute the LangGraph weather agent for a user query.

    Args:
        query: User's natural-language meteorological inquiry.
        llm_client: Optional LLM client instance (for testing/mocking).
        weather_service: Optional WeatherService instance.
        statistics_service: Optional StatisticsService instance.

    Returns:
        Final WeatherAgentState dictionary containing extracted intent, city,
        retrieved weather data, canonical result, and synthesized response.
    """
    if llm_client is not None or weather_service is not None or statistics_service is not None:
        graph = create_weather_agent_graph(
            llm_client=llm_client,
            weather_service=weather_service,
            statistics_service=statistics_service,
        )
    else:
        graph = default_weather_agent_graph

    initial_state: WeatherAgentState = {
        "query": query,
        "city": None,
        "intent": None,
        "parameters": {},
        "weather_data": None,
        "result": None,
        "response": None,
        "error": None,
    }

    final_state = graph.invoke(initial_state)
    return final_state
