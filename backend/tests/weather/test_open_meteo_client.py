"""Unit tests for OpenMeteoClient (both current/forecast client and historical archive client)."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.clients.open_meteo_client import OpenMeteoClient as ForecastClient
from app.clients.weather_client import (
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.services.weather.open_meteo_client import OpenMeteoClient as HistoricalOpenMeteoClient


@pytest.fixture
def forecast_client() -> ForecastClient:
    return ForecastClient()


@pytest.fixture
def historical_client() -> HistoricalOpenMeteoClient:
    return HistoricalOpenMeteoClient()


# ---------------------------------------------------------------------------
# ForecastClient tests (existing functionality preserved)
# ---------------------------------------------------------------------------

@patch("httpx.Client.get")
def test_geocode_city_success(mock_get: MagicMock, forecast_client: ForecastClient) -> None:
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

    result = forecast_client.geocode_city("Indore")
    assert result["latitude"] == 22.7179
    assert result["longitude"] == 75.8333
    assert result["formatted_address"] == "Indore, Madhya Pradesh, India"


@patch("httpx.Client.get")
def test_geocode_city_not_found(mock_get: MagicMock, forecast_client: ForecastClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    with pytest.raises(CityNotFoundError, match="City 'NonExistent' not found"):
        forecast_client.geocode_city("NonExistent")


@patch("httpx.Client.get")
def test_get_current_conditions_success(mock_get: MagicMock, forecast_client: ForecastClient) -> None:
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

    conditions = forecast_client.get_current_conditions(22.7179, 75.8333)
    assert conditions["temperature"]["degrees"] == 31.5
    assert conditions["feelsLikeTemperature"]["degrees"] == 33.0
    assert conditions["relativeHumidity"] == 40
    assert conditions["wind"]["speed"]["value"] == 8.5
    assert conditions["weatherCondition"]["description"]["text"] == "Clear sky"


@patch("httpx.Client.get")
def test_get_forecast_success(mock_get: MagicMock, forecast_client: ForecastClient) -> None:
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

    result = forecast_client.get_forecast(22.7179, 75.8333, days=2)
    assert "forecast" in result
    assert len(result["forecast"]) == 2
    assert result["forecast"][0]["temperature_max"] == 33.0
    assert result["forecast"][0]["condition"] == "Clear sky"
    assert result["forecast"][1]["condition"] == "Partly cloudy"


# ---------------------------------------------------------------------------
# HistoricalOpenMeteoClient tests (Geocoding with Timezone & Historical Archive)
# ---------------------------------------------------------------------------

@patch("httpx.Client.get")
def test_historical_client_geocode_with_timezone(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "name": "Indore",
                "latitude": 22.7179,
                "longitude": 75.8333,
                "timezone": "Asia/Kolkata",
                "admin1": "Madhya Pradesh",
                "country": "India",
            }
        ]
    }
    mock_get.return_value = mock_response

    loc = historical_client.geocode_city("Indore")
    assert loc["city"] == "Indore"
    assert loc["latitude"] == 22.7179
    assert loc["longitude"] == 75.8333
    assert loc["timezone"] == "Asia/Kolkata"
    assert mock_get.call_count == 1

    # Second call should use in-memory cache
    cached_loc = historical_client.geocode_city("indore")
    assert cached_loc["city"] == "Indore"
    assert mock_get.call_count == 1


def test_historical_client_geocode_empty_city(
    historical_client: HistoricalOpenMeteoClient,
) -> None:
    with pytest.raises(CityNotFoundError, match="City name cannot be empty"):
        historical_client.geocode_city("")

    with pytest.raises(CityNotFoundError, match="City name cannot be empty"):
        historical_client.geocode_city("   ")


@patch("httpx.Client.get")
def test_historical_client_geocode_not_found(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_get.return_value = mock_response

    with pytest.raises(CityNotFoundError, match="City 'NonexistentCity' not found"):
        historical_client.geocode_city("NonexistentCity")


@patch("httpx.Client.get")
def test_historical_client_geocode_timeout(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_get.side_effect = httpx.TimeoutException("Timed out")
    with pytest.raises(WeatherTimeoutError, match="timed out"):
        historical_client.geocode_city("Indore")


@patch("httpx.Client.get")
def test_historical_client_geocode_network_error(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_get.side_effect = httpx.RequestError("Network error")
    with pytest.raises(WeatherServiceUnavailableError, match="Unable to connect"):
        historical_client.geocode_city("Indore")


@patch("httpx.Client.get")
def test_historical_client_geocode_rate_limit(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_get.return_value = mock_response

    with pytest.raises(WeatherRateLimitError, match="rate limit exceeded"):
        historical_client.geocode_city("Indore")


@patch("httpx.Client.get")
def test_historical_client_archive_success(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "daily": {
            "time": ["2026-09-25", "2026-09-26", "2026-09-27"],
            "temperature_2m_mean": [28.5, 29.0, 27.5],
        }
    }
    mock_get.return_value = mock_response

    res = historical_client.get_historical_weather(
        latitude=22.7179,
        longitude=75.8333,
        start_date="2026-09-25",
        end_date="2026-09-27",
        timezone="Asia/Kolkata",
    )
    assert len(res["time"]) == 3
    assert res["temperature_2m_mean"] == [28.5, 29.0, 27.5]


@patch("httpx.Client.get")
def test_historical_client_archive_timeout(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_get.side_effect = httpx.TimeoutException("Timed out")
    with pytest.raises(WeatherTimeoutError, match="timed out"):
        historical_client.get_historical_weather(22.7179, 75.8333, "2026-09-25", "2026-10-02")


@patch("httpx.Client.get")
def test_historical_client_archive_server_error(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_get.return_value = mock_response

    with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
        historical_client.get_historical_weather(22.7179, 75.8333, "2026-09-25", "2026-10-02")


@patch("httpx.Client.get")
def test_historical_client_archive_malformed_json(
    mock_get: MagicMock, historical_client: HistoricalOpenMeteoClient
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "no daily key"}
    mock_get.return_value = mock_response

    with pytest.raises(WeatherResponseParsingError, match="Unexpected format"):
        historical_client.get_historical_weather(22.7179, 75.8333, "2026-09-25", "2026-10-02")
