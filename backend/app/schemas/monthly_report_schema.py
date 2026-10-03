"""Pydantic schemas for the Monthly Weather Report feature."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WeeklyPeriodReport(BaseModel):
    """Calculated metrics for a single weekly period within a month."""

    week: str = Field(
        ...,
        description="Period name (e.g. 'Week 1', 'Week 2', 'Week 3', 'Week 4', 'Remaining Days')",
        examples=["Week 1", "Remaining Days"],
    )
    date_range: str = Field(
        ...,
        description="Formatted date range (e.g. 'Aug 1 - Aug 7', 'Aug 29 - Aug 31')",
        examples=["Aug 1 - Aug 7"],
    )
    start_date: str = Field(
        ...,
        description="Period start date in ISO format (YYYY-MM-DD)",
        examples=["2026-08-01"],
    )
    end_date: str = Field(
        ...,
        description="Period end date in ISO format (YYYY-MM-DD)",
        examples=["2026-08-07"],
    )
    average_temperature: Optional[float] = Field(
        None,
        description="Deterministic average temperature in Celsius rounded to 1 decimal place",
        examples=[26.4],
    )
    observation_count: int = Field(
        ...,
        description="Count of valid daily observations recorded in this period",
        examples=[7],
    )
    expected_days: int = Field(
        ...,
        description="Total calendar days in this period",
        examples=[7],
    )
    is_complete: bool = Field(
        True,
        description="Whether all days in the period have valid observations",
        examples=[True],
    )
    note: Optional[str] = Field(
        None,
        description="Informative note if data is incomplete or missing",
        examples=["Incomplete data (5/7 days)"],
    )


class MonthlyWeatherReportResponse(BaseModel):
    """Complete Monthly Weather Report structure."""

    city: str = Field(
        ...,
        description="Target city name and regional context (e.g. 'Indore, Madhya Pradesh')",
        examples=["Indore, Madhya Pradesh"],
    )
    month: str = Field(
        ...,
        description="Formatted month and year (e.g. 'August 2026')",
        examples=["August 2026"],
    )
    year: int = Field(
        ...,
        description="Calendar year",
        examples=[2026],
    )
    month_number: int = Field(
        ...,
        description="Month number (1-12)",
        examples=[8],
    )
    weekly_averages: List[WeeklyPeriodReport] = Field(
        default_factory=list,
        description="Deterministic weekly period calculations",
    )
    summary: Optional[str] = Field(
        None,
        description="AI-generated professional meteorological summary (2-4 sentences)",
        examples=[
            "Indore experienced relatively stable temperatures during August 2026. "
            "The highest weekly average temperature was 26.4°C during Week 1, while "
            "the lowest was 24.9°C during Week 3. Overall, temperatures remained fairly "
            "consistent throughout the analyzed period."
        ],
    )
    status: str = Field(
        "SUCCESS",
        description="Report status ('SUCCESS', 'PARTIAL_SUCCESS', 'UNAVAILABLE')",
        examples=["SUCCESS"],
    )
    message: Optional[str] = Field(
        None,
        description="User-facing status message if data is unavailable or partially available",
    )
    highest_week: Optional[Dict[str, Any]] = Field(
        None,
        description="Pre-calculated highest weekly period info",
    )
    lowest_week: Optional[Dict[str, Any]] = Field(
        None,
        description="Pre-calculated lowest weekly period info",
    )
    email_payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured data reserved for future email report generation service",
    )


class MonthlyWeatherReportRequest(BaseModel):
    """Request payload for POST /api/v1/weather/report/monthly."""

    city: str = Field(..., description="Target city name", examples=["Indore"])
    month: Optional[str] = Field(None, description="Month name or string (e.g. 'August 2026')", examples=["August 2026"])
    year: Optional[int] = Field(None, description="Year integer (e.g. 2026)", examples=[2026])
    month_num: Optional[int] = Field(None, description="Month number (1-12)", examples=[8])
