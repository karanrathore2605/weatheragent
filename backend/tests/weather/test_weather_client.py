"""Unit tests for GoogleWeatherClient with mocked HTTP transport."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.clients.weather_client import (
    GoogleWeatherClient,
    CityNotFoundError,
    WeatherAuthenticationError,
    WeatherRateLimitError,
    WeatherTimeoutError,
    WeatherServiceUnavailableError,
    WeatherResponseParsingError,
)


@pytest.fixture
def client_with_key() -> GoogleWeatherClient:
    """Fixture providing a GoogleWeatherClient configured with a mock API key."""
    return GoogleWeatherClient(api_key="mock-api-key")


def test_missing_api_key_raises_auth_error() -> None:
    """Ensure client raises WeatherAuthenticationError when api_key is empty."""
    client = GoogleWeatherClient(api_key="")
    with pytest.raises(WeatherAuthenticationError, match="API key is not configured"):
        client.geocode_city("Indore")

    with pytest.raises(WeatherAuthenticationError, match="API key is not configured"):
        client.get_current_conditions(22.7196, 75.8577)


@patch("httpx.Client.get")
def test_geocode_city_success(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test successful geocoding resolution for a valid city."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "Indore, Madhya Pradesh, India",
                "geometry": {
                    "location": {
                        "lat": 22.7196,
                        "lng": 75.8577,
                    }
                },
            }
        ],
    }
    mock_get.return_value = mock_response

    result = client_with_key.geocode_city("Indore")

    assert result["latitude"] == 22.7196
    assert result["longitude"] == 75.8577
    assert result["formatted_address"] == "Indore, Madhya Pradesh, India"


@patch("httpx.Client.get")
def test_geocode_city_zero_results(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that ZERO_RESULTS raises CityNotFoundError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "ZERO_RESULTS",
        "results": [],
    }
    mock_get.return_value = mock_response

    with pytest.raises(CityNotFoundError, match="City 'NonExistentPlace' not found"):
        client_with_key.geocode_city("NonExistentPlace")


@patch("httpx.Client.get")
def test_geocode_city_request_denied(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that REQUEST_DENIED raises WeatherAuthenticationError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "REQUEST_DENIED",
        "error_message": "The provided API key is invalid.",
    }
    mock_get.return_value = mock_response

    with pytest.raises(WeatherAuthenticationError, match="Check API credentials"):
        client_with_key.geocode_city("Indore")


@patch("httpx.Client.get")
def test_geocode_city_rate_limit(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that OVER_QUERY_LIMIT raises WeatherRateLimitError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OVER_QUERY_LIMIT",
    }
    mock_get.return_value = mock_response

    with pytest.raises(WeatherRateLimitError, match="Location service quota exceeded"):
        client_with_key.geocode_city("Indore")


@patch("httpx.Client.get")
def test_geocode_city_timeout(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that network timeout raises WeatherTimeoutError."""
    mock_get.side_effect = httpx.TimeoutException("Connection timed out")

    with pytest.raises(WeatherTimeoutError, match="timed out"):
        client_with_key.geocode_city("Indore")


@patch("httpx.Client.get")
def test_geocode_city_network_error(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that network request failure raises WeatherServiceUnavailableError."""
    mock_get.side_effect = httpx.RequestError("Connection failed")

    with pytest.raises(WeatherServiceUnavailableError, match="Unable to connect"):
        client_with_key.geocode_city("Indore")


@patch("httpx.Client.get")
def test_get_current_conditions_success(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test successful current conditions retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "currentTime": "2026-10-01T10:30:00Z",
        "temperature": {"degrees": 28.4},
        "feelsLikeTemperature": {"degrees": 30.1},
        "relativeHumidity": 65,
        "wind": {"speed": {"value": 12.2}},
        "weatherCondition": {"description": {"text": "Partly Cloudy"}},
    }
    mock_get.return_value = mock_response

    result = client_with_key.get_current_conditions(22.7196, 75.8577)

    assert result["temperature"]["degrees"] == 28.4
    assert result["weatherCondition"]["description"]["text"] == "Partly Cloudy"


@patch("httpx.Client.get")
def test_get_current_conditions_auth_failure(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that HTTP 401 raises WeatherAuthenticationError."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    with pytest.raises(WeatherAuthenticationError, match="authentication failed"):
        client_with_key.get_current_conditions(22.7196, 75.8577)


@patch("httpx.Client.get")
def test_get_current_conditions_rate_limit(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that HTTP 429 raises WeatherRateLimitError."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_get.return_value = mock_response

    with pytest.raises(WeatherRateLimitError, match="rate limit exceeded"):
        client_with_key.get_current_conditions(22.7196, 75.8577)


@patch("httpx.Client.get")
def test_get_current_conditions_server_error(mock_get: MagicMock, client_with_key: GoogleWeatherClient) -> None:
    """Test that HTTP 500 raises WeatherServiceUnavailableError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    with pytest.raises(WeatherServiceUnavailableError, match="temporarily unavailable"):
        client_with_key.get_current_conditions(22.7196, 75.8577)
