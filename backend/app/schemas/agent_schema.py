"""Pydantic schemas for the LangGraph Weather Agent endpoints."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Natural-language query payload sent to the LangGraph weather agent."""

    query: str = Field(
        ...,
        description="Natural-language weather question or instruction",
        examples=["What is the weather in Indore?"],
    )


class AgentQueryResponse(BaseModel):
    """Structured response payload returned by the LangGraph weather agent."""

    query: str = Field(..., description="Original user query")
    city: Optional[str] = Field(None, description="Extracted target city name")
    intent: Optional[str] = Field(None, description="Classified intent route")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parsed parameters")
    weather_data: Optional[Dict[str, Any]] = Field(None, description="Verified meteorological data")
    result: Optional[Dict[str, Any]] = Field(None, description="Canonical normalized data payload")
    response: str = Field(..., description="Professional meteorological report or friendly guidance")
    error: Optional[str] = Field(None, description="Standardized error code if any")
