"""Unit tests for HistoricalWeatherService with mocked Open-Meteo client."""

from unittest.mock import MagicMock
import pytest

from app.clients.weather_client import (
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.services.historical_weather_service import HistoricalWeatherService
from app.services.weather.open_meteo_client import OpenMeteoClient


@pytest.fixture
def mock_open_meteo_client() -> MagicMock:
    client = MagicMock(spec=OpenMeteoClient)
    client.geocode_city.return_value = {
        "city": "Indore",
        "name": "Indore",
        "latitude": 22.7179,
        "longitude": 75.8333,
        "timezone": "Asia/Kolkata",
        "formatted_address": "Indore, Madhya Pradesh, India",
    }
    client.get_historical_weather.return_value = {
        "time": ["2026-09-25", "2026-09-26", "2026-09-27"],
        "temperature_2m_mean": [28.5, 29.0, 27.5],
    }
    return client


@pytest.fixture
def historical_service(mock_open_meteo_client: MagicMock) -> HistoricalWeatherService:
    return HistoricalWeatherService(open_meteo_client=mock_open_meteo_client)


def test_fetch_historical_temperatures_success(
    historical_service: HistoricalWeatherService,
    mock_open_meteo_client: MagicMock,
) -> None:
    res = historical_service.fetch_historical_temperatures("Indore", "2026-09-25", "2026-09-27")

    mock_open_meteo_client.geocode_city.assert_called_once_with("Indore")
    mock_open_meteo_client.get_historical_weather.assert_called_once_with(
        latitude=22.7179,
        longitude=75.8333,
        start_date="2026-09-25",
        end_date="2026-09-27",
        timezone="Asia/Kolkata",
    )

    assert res["city"] == "Indore"
    assert res["dates"] == ["2026-09-25", "2026-09-26", "2026-09-27"]
    assert res["temperatures"] == [28.5, 29.0, 27.5]


def test_historical_service_timeout(
    historical_service: HistoricalWeatherService,
    mock_open_meteo_client: MagicMock,
) -> None:
    mock_open_meteo_client.get_historical_weather.side_effect = WeatherTimeoutError("Request timed out.")
    with pytest.raises(WeatherTimeoutError, match="timed out"):
        historical_service.fetch_historical_temperatures("Indore", "2026-09-25", "2026-09-27")


def test_historical_service_city_not_found(
    historical_service: HistoricalWeatherService,
    mock_open_meteo_client: MagicMock,
) -> None:
    mock_open_meteo_client.geocode_city.side_effect = CityNotFoundError("City 'Nonexistent' not found.")
    with pytest.raises(CityNotFoundError, match="not found"):
        historical_service.fetch_historical_temperatures("Nonexistent", "2026-09-25", "2026-09-27")


def test_historical_service_service_unavailable(
    historical_service: HistoricalWeatherService,
    mock_open_meteo_client: MagicMock,
) -> None:
    mock_open_meteo_client.get_historical_weather.side_effect = WeatherServiceUnavailableError("Service down.")
    with pytest.raises(WeatherServiceUnavailableError, match="Service down"):
        historical_service.fetch_historical_temperatures("Indore", "2026-09-25", "2026-09-27")
