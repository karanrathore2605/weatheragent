"""API Router exposing the LangGraph Weather Agent workflow."""

from typing import Optional
from fastapi import APIRouter, Query, status

from app.agents.weather_agent_graph import run_weather_agent
from app.schemas.agent_schema import AgentQueryRequest, AgentQueryResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["LangGraph Agent"],
)


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the LangGraph Weather Agent",
    description="Processes natural-language weather queries using LangGraph conditional routing and Groq LLM.",
)
def process_agent_query(payload: AgentQueryRequest) -> AgentQueryResponse:
    """Execute LangGraph workflow for a POST request."""
    logger.info("Received POST /agent/query: '%s'", payload.query)
    final_state = run_weather_agent(query=payload.query)

    return AgentQueryResponse(
        query=final_state.get("query", payload.query),
        city=final_state.get("city"),
        intent=final_state.get("intent"),
        parameters=final_state.get("parameters") or {},
        weather_data=final_state.get("weather_data"),
        result=final_state.get("result"),
        response=final_state.get("response") or "",
        error=final_state.get("error"),
    )


@router.get(
    "/query",
    response_model=AgentQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the LangGraph Weather Agent via GET",
    description="Convenience GET endpoint to ask natural-language questions via query string.",
)
def query_agent_get(
    q: str = Query(..., description="Natural language weather inquiry", examples=["What is the weather in Indore?"])
) -> AgentQueryResponse:
    """Execute LangGraph workflow for a GET request."""
    logger.info("Received GET /agent/query?q=%s", q)
    final_state = run_weather_agent(query=q)

    return AgentQueryResponse(
        query=final_state.get("query", q),
        city=final_state.get("city"),
        intent=final_state.get("intent"),
        parameters=final_state.get("parameters") or {},
        weather_data=final_state.get("weather_data"),
        result=final_state.get("result"),
        response=final_state.get("response") or "",
        error=final_state.get("error"),
    )
