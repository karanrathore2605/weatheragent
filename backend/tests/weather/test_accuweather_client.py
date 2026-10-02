"""Unit tests for AccuWeatherClient mocking HTTP interactions."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.clients.accuweather_client import AccuWeatherClient
from app.clients.weather_client import (
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)


@pytest.fixture
def client() -> AccuWeatherClient:
    return AccuWeatherClient(api_key="test-api-key", timeout=5.0, base_url="http://dataservice.accuweather.com")


# ---------------------------------------------------------------------------
# Location Search Tests
# ---------------------------------------------------------------------------

def test_search_location_success(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "Key": "202441",
            "LocalizedName": "Indore",
            "AdministrativeArea": {"LocalizedName": "Madhya Pradesh"},
            "Country": {"LocalizedName": "India"},
            "GeoPosition": {"Latitude": 22.7196, "Longitude": 75.8577},
        }
    ]

    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        loc = client.search_location("Indore")
        assert loc["key"] == "202441"
        assert loc["city"] == "Indore"
        assert loc["latitude"] == 22.7196
        assert loc["longitude"] == 75.8577
        assert "Indore" in loc["formatted_address"]
        assert mock_get.call_count == 1

        # Test caching: Second call should hit the cache and not invoke HTTP GET
        cached_loc = client.search_location("Indore")
        assert cached_loc["key"] == "202441"
        assert mock_get.call_count == 1


def test_search_location_empty_city(client: AccuWeatherClient) -> None:
    with pytest.raises(CityNotFoundError, match="City name cannot be empty"):
        client.search_location("")

    with pytest.raises(CityNotFoundError, match="City name cannot be empty"):
        client.search_location("   ")


def test_search_location_missing_api_key() -> None:
    unauthenticated_client = AccuWeatherClient(api_key="", base_url="http://dataservice.accuweather.com")
    with pytest.raises(WeatherAuthenticationError, match="API key is not configured"):
        unauthenticated_client.search_location("Indore")


def test_search_location_auth_failure(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherAuthenticationError, match="authentication failed"):
            client.search_location("Indore")


def test_search_location_not_found(client: AccuWeatherClient) -> None:
    # 404 response
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404

    with patch("httpx.Client.get", return_value=mock_response_404):
        with pytest.raises(CityNotFoundError, match="not found"):
            client.search_location("UnknownCity123")

    # Empty list response
    mock_response_empty = MagicMock()
    mock_response_empty.status_code = 200
    mock_response_empty.json.return_value = []

    with patch("httpx.Client.get", return_value=mock_response_empty):
        with pytest.raises(CityNotFoundError, match="not found"):
            client.search_location("UnknownCity456")


def test_search_location_rate_limit(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherRateLimitError, match="rate limit exceeded"):
            client.search_location("Indore")


def test_search_location_service_unavailable(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
            client.search_location("Indore")


def test_search_location_timeout(client: AccuWeatherClient) -> None:
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(WeatherTimeoutError, match="timed out"):
            client.search_location("Indore")


def test_search_location_network_error(client: AccuWeatherClient) -> None:
    with patch("httpx.Client.get", side_effect=httpx.RequestError("Network is down")):
        with pytest.raises(WeatherServiceUnavailableError, match="Unable to reach"):
            client.search_location("Indore")


def test_search_location_malformed_json(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON format")

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherResponseParsingError, match="Invalid JSON"):
            client.search_location("Indore")


# ---------------------------------------------------------------------------
# Historical Conditions Tests
# ---------------------------------------------------------------------------

def test_get_historical_conditions_success(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "LocalObservationDateTime": "2026-10-02T12:00:00+05:30",
            "EpochTime": 1790924400,
            "WeatherText": "Sunny",
            "Temperature": {"Metric": {"Value": 31.8, "Unit": "C"}},
            "RealFeelTemperature": {"Metric": {"Value": 33.0, "Unit": "C"}},
            "RelativeHumidity": 45,
        }
    ]

    with patch("httpx.Client.get", return_value=mock_response):
        history = client.get_historical_conditions("202441", hours=24)
        assert len(history) == 1
        assert history[0]["WeatherText"] == "Sunny"
        assert history[0]["Temperature"]["Metric"]["Value"] == 31.8


def test_get_historical_conditions_auth_failure(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherAuthenticationError, match="authentication failed"):
            client.get_historical_conditions("202441")


def test_get_historical_conditions_not_found(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(CityNotFoundError, match="not found"):
            client.get_historical_conditions("999999999")


def test_get_historical_conditions_rate_limit(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 429

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherRateLimitError, match="rate limit"):
            client.get_historical_conditions("202441")


def test_get_historical_conditions_server_error(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
            client.get_historical_conditions("202441")


def test_get_historical_conditions_timeout(client: AccuWeatherClient) -> None:
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timed out")):
        with pytest.raises(WeatherTimeoutError, match="timed out"):
            client.get_historical_conditions("202441")


def test_get_historical_conditions_malformed_json(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Corrupt body")

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherResponseParsingError, match="Invalid JSON"):
            client.get_historical_conditions("202441")


def test_get_historical_conditions_not_a_list(client: AccuWeatherClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "unexpected format"}

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(WeatherResponseParsingError, match="Unexpected data format"):
            client.get_historical_conditions("202441")
