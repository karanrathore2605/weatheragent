"""Unit tests for country/region-aware location resolution service."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.clients.weather_client import (
    AmbiguousLocationError,
    CityNotFoundError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.services.location_service import (
    LocationResolver,
    format_location_address,
    normalize_name,
    select_best_candidate,
)


@pytest.fixture
def resolver() -> LocationResolver:
    """Fresh LocationResolver instance with empty cache."""
    return LocationResolver()


class TestAddressFormatting:
    """Test address formatting for canonical UX requirements."""

    def test_delhi_formatting(self) -> None:
        addr = format_location_address("Delhi", "National Capital Territory of Delhi", "India", "IN")
        assert addr == "Delhi, India"

    def test_leh_formatting(self) -> None:
        addr = format_location_address("Leh", "Ladakh", "India", "IN")
        assert addr == "Leh, Ladakh, India"

    def test_indore_formatting(self) -> None:
        addr = format_location_address("Indore", "Madhya Pradesh", "India", "IN")
        assert addr == "Indore, Madhya Pradesh, India"

    def test_bhopal_formatting(self) -> None:
        addr = format_location_address("Bhopal", "Madhya Pradesh", "India", "IN")
        assert addr == "Bhopal, Madhya Pradesh, India"

    def test_mumbai_formatting(self) -> None:
        addr = format_location_address("Mumbai", "Maharashtra", "India", "IN")
        assert addr == "Mumbai, Maharashtra, India"

    def test_le_havre_formatting(self) -> None:
        addr = format_location_address("Le Havre", "Normandy", "France", "FR")
        assert addr == "Le Havre, Normandy, France"


class TestCandidateSelection:
    """Test candidate ranking, exact match prioritization, and ambiguity detection."""

    def test_leh_selects_ladakh_india_over_le_havre(self) -> None:
        """When searching for 'Leh', 'Le Havre' (France) must NOT be selected."""
        results = [
            {
                "id": 1,
                "name": "Le Havre",
                "latitude": 49.49346,
                "longitude": 0.10785,
                "country": "France",
                "country_code": "FR",
                "admin1": "Normandy",
                "population": 185972,
            },
            {
                "id": 2,
                "name": "Leh",
                "latitude": 34.16504,
                "longitude": 77.58402,
                "country": "India",
                "country_code": "IN",
                "admin1": "Ladakh",
                "population": 37475,
            },
            {
                "id": 3,
                "name": "Leh",
                "latitude": 47.38333,
                "longitude": 13.15,
                "country": "Austria",
                "country_code": "AT",
                "admin1": "State of Salzburg",
                "population": 0,
            },
        ]
        best = select_best_candidate("Leh", results)
        assert best["id"] == 2
        assert best["name"] == "Leh"
        assert best["country_code"] == "IN"
        assert best["admin1"] == "Ladakh"

    def test_le_havre_selects_france(self) -> None:
        results = [
            {
                "id": 1,
                "name": "Le Havre",
                "latitude": 49.49346,
                "longitude": 0.10785,
                "country": "France",
                "country_code": "FR",
                "admin1": "Normandy",
                "population": 185972,
            },
        ]
        best = select_best_candidate("Le Havre", results)
        assert best["name"] == "Le Havre"
        assert best["country_code"] == "FR"

    def test_ambiguous_location_raises_error(self) -> None:
        """Multiple distinct exact matches with comparable population raise AmbiguousLocationError."""
        results = [
            {
                "name": "Springfield",
                "latitude": 37.2089,
                "longitude": -93.2923,
                "country": "United States",
                "country_code": "US",
                "admin1": "Missouri",
                "population": 170000,
            },
            {
                "name": "Springfield",
                "latitude": 42.1015,
                "longitude": -72.5898,
                "country": "United States",
                "country_code": "US",
                "admin1": "Massachusetts",
                "population": 155000,
            },
            {
                "name": "Springfield",
                "latitude": 39.7817,
                "longitude": -89.6501,
                "country": "United States",
                "country_code": "US",
                "admin1": "Illinois",
                "population": 114000,
            },
        ]
        with pytest.raises(AmbiguousLocationError) as exc_info:
            select_best_candidate("Springfield", results)
        assert "Multiple locations match 'Springfield'" in str(exc_info.value)
        assert "specify the country or region" in str(exc_info.value)

    def test_qualified_location_resolves_ambiguity(self) -> None:
        """When user provides qualifier (e.g. 'Springfield, Illinois'), ambiguity is resolved."""
        results = [
            {
                "name": "Springfield",
                "latitude": 37.2089,
                "longitude": -93.2923,
                "country": "United States",
                "country_code": "US",
                "admin1": "Missouri",
                "population": 170000,
            },
            {
                "name": "Springfield",
                "latitude": 39.7817,
                "longitude": -89.6501,
                "country": "United States",
                "country_code": "US",
                "admin1": "Illinois",
                "population": 114000,
            },
        ]
        best = select_best_candidate("Springfield, Illinois", results)
        assert best["admin1"] == "Illinois"


class TestLocationResolverFlow:
    """Test full resolve_location workflow with caching, aliases, and mocking."""

    def test_empty_city_raises_city_not_found(self, resolver: LocationResolver) -> None:
        with pytest.raises(CityNotFoundError, match="cannot be empty"):
            resolver.resolve_location("")

        with pytest.raises(CityNotFoundError, match="cannot be empty"):
            resolver.resolve_location("   ")

    @patch("httpx.Client.get")
    def test_leh_resolution(self, mock_get: MagicMock, resolver: LocationResolver) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "name": "Le Havre",
                    "latitude": 49.49346,
                    "longitude": 0.10785,
                    "country": "France",
                    "country_code": "FR",
                    "admin1": "Normandy",
                    "population": 185972,
                },
                {
                    "name": "Leh",
                    "latitude": 34.16504,
                    "longitude": 77.58402,
                    "country": "India",
                    "country_code": "IN",
                    "admin1": "Ladakh",
                    "timezone": "Asia/Kolkata",
                    "population": 37475,
                },
            ]
        }
        mock_get.return_value = mock_resp

        loc = resolver.resolve_location("Leh")
        assert loc["city"] == "Leh"
        assert loc["latitude"] == 34.16504
        assert loc["longitude"] == 77.58402
        assert loc["formatted_address"] == "Leh, Ladakh, India"

    @patch("httpx.Client.get")
    def test_indian_city_alias_bombay(self, mock_get: MagicMock, resolver: LocationResolver) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "name": "Mumbai",
                    "latitude": 19.07283,
                    "longitude": 72.88261,
                    "country": "India",
                    "country_code": "IN",
                    "admin1": "Maharashtra",
                    "timezone": "Asia/Kolkata",
                    "population": 12691836,
                },
            ]
        }
        mock_get.return_value = mock_resp

        loc = resolver.resolve_location("Bombay")
        assert loc["city"] == "Mumbai"
        assert loc["formatted_address"] == "Mumbai, Maharashtra, India"

    @patch("httpx.Client.get")
    def test_city_not_found(self, mock_get: MagicMock, resolver: LocationResolver) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_get.return_value = mock_resp

        with pytest.raises(CityNotFoundError, match="City 'NonexistentCityXYZ' not found"):
            resolver.resolve_location("NonexistentCityXYZ")
