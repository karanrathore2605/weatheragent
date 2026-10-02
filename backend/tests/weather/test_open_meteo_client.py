"""Unit tests for OpenMeteoClient."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.clients.open_meteo_client import OpenMeteoClient
from app.clients.weather_client import (
    CityNotFoundError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)


@pytest.fixture
def open_meteo_client() -> OpenMeteoClient:
    """Fixture providing an OpenMeteoClient instance."""
    return OpenMeteoClient()


@patch("httpx.Client.get")
def test_geocode_city_success(mock_get: MagicMock, open_meteo_client: OpenMeteoClient) -> None:
    """Test successful geocoding resolution for OpenMeteo."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "name": "Indore",
                "latitude": 22.7179,
                "longitude": 75.8333,
                "admin1": "Madhya Pradesh",
                "country": "India",
            }
        ]
    }
    mock_get.return_value = mock_response

    result = open_meteo_client.geocode_city("Indore")
    assert result["latitude"] == 22.7179
    assert result["longitude"] == 75.8333
    assert result["formatted_address"] == "Indore, Madhya Pradesh, India"


@patch("httpx.Client.get")
def test_geocode_city_not_found(mock_get: MagicMock, open_meteo_client: OpenMeteoClient) -> None:
    """Test geocoding returns CityNotFoundError when results is empty."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    with pytest.raises(CityNotFoundError, match="City 'NonExistent' not found"):
        open_meteo_client.geocode_city("NonExistent")


@patch("httpx.Client.get")
def test_get_current_conditions_success(mock_get: MagicMock, open_meteo_client: OpenMeteoClient) -> None:
    """Test successful current weather lookup."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "current": {
            "time": "2026-10-02T11:30",
            "temperature_2m": 31.5,
            "apparent_temperature": 33.0,
            "relative_humidity_2m": 40,
            "wind_speed_10m": 8.5,
            "weather_code": 0,
        }
    }
    mock_get.return_value = mock_response

    conditions = open_meteo_client.get_current_conditions(22.7179, 75.8333)
    assert conditions["temperature"]["degrees"] == 31.5
    assert conditions["feelsLikeTemperature"]["degrees"] == 33.0
    assert conditions["relativeHumidity"] == 40
    assert conditions["wind"]["speed"]["value"] == 8.5
    assert conditions["weatherCondition"]["description"]["text"] == "Clear sky"


@patch("httpx.Client.get")
def test_get_forecast_success(mock_get: MagicMock, open_meteo_client: OpenMeteoClient) -> None:
    """Test successful multi-day forecast retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "daily": {
            "time": ["2026-10-02", "2026-10-03"],
            "weather_code": [0, 2],
            "temperature_2m_max": [33.0, 31.5],
            "temperature_2m_min": [22.0, 21.0],
            "precipitation_probability_max": [5, 20],
            "relative_humidity_2m_mean": [40, 50],
            "wind_speed_10m_max": [10.0, 12.0],
        }
    }
    mock_get.return_value = mock_response

    result = open_meteo_client.get_forecast(22.7179, 75.8333, days=2)
    assert "forecast" in result
    assert len(result["forecast"]) == 2
    assert result["forecast"][0]["temperature_max"] == 33.0
    assert result["forecast"][0]["condition"] == "Clear sky"
    assert result["forecast"][1]["condition"] == "Partly cloudy"
