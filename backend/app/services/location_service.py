"""Intelligent, country/region-aware location resolution service.

Features:
- Exact city name matching over fuzzy partial matching
- Country/region-aware candidate prioritization (e.g. Leh, Ladakh, India vs Le Havre, France)
- Indian city aliases (e.g. Bombay -> Mumbai, Bangalore -> Bengaluru)
- Canonical address formatting (e.g. Delhi, India; Leh, Ladakh, India)
- Ambiguity detection with clear user instructions
- In-memory caching and resilient fallback
"""

from typing import Any, Dict, List, Optional
import unicodedata
import httpx

from app.clients.weather_client import (
    AmbiguousLocationError,
    CityNotFoundError,
    WeatherRateLimitError,
    WeatherResponseParsingError,
    WeatherServiceUnavailableError,
    WeatherTimeoutError,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Common Indian city name variations, historical colonial names, and informal aliases
INDIAN_CITY_ALIASES: Dict[str, str] = {
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "bangalore": "Bengaluru",
    "poona": "Pune",
    "banaras": "Varanasi",
    "benares": "Varanasi",
    "kashi": "Varanasi",
    "baroda": "Vadodara",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "gurgaon": "Gurugram",
    "allahabad": "Prayagraj",
    "pondicherry": "Puducherry",
    "calicut": "Kozhikode",
    "mangalore": "Mangaluru",
    "belgaum": "Belagavi",
    "mysore": "Mysuru",
    "hubli": "Hubballi",
    "simla": "Shimla",
    "gauhati": "Guwahati",
    "vizag": "Visakhapatnam",
    "waltair": "Visakhapatnam",
    "new delhi": "Delhi",
}

# Pre-configured canonical coordinates and address formatting for common Indian cities
WELL_KNOWN_INDIAN_CITIES: Dict[str, Dict[str, Any]] = {
    "leh": {
        "name": "Leh",
        "latitude": 34.16504,
        "longitude": 77.58402,
        "admin1": "Ladakh",
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "formatted_address": "Leh, Ladakh, India",
    },
    "indore": {
        "name": "Indore",
        "latitude": 22.71792,
        "longitude": 75.8333,
        "admin1": "Madhya Pradesh",
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "formatted_address": "Indore, Madhya Pradesh, India",
    },
    "bhopal": {
        "name": "Bhopal",
        "latitude": 23.25469,
        "longitude": 77.40289,
        "admin1": "Madhya Pradesh",
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "formatted_address": "Bhopal, Madhya Pradesh, India",
    },
    "mumbai": {
        "name": "Mumbai",
        "latitude": 19.07283,
        "longitude": 72.88261,
        "admin1": "Maharashtra",
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "formatted_address": "Mumbai, Maharashtra, India",
    },
    "delhi": {
        "name": "Delhi",
        "latitude": 28.65195,
        "longitude": 77.23149,
        "admin1": "National Capital Territory of Delhi",
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "formatted_address": "Delhi, India",
    },
}


def normalize_name(text: Optional[str]) -> str:
    """Normalize text by stripping diacritics, lowering case, and trimming spaces."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    ).lower().strip()


def format_location_address(
    name: str,
    admin1: Optional[str] = None,
    country: Optional[str] = None,
    country_code: Optional[str] = None,
) -> str:
    """Format human-readable location address strictly matching canonical standards.
    
    Rules:
    - "Delhi" -> "Delhi, India" (avoid redundant "National Capital Territory of Delhi")
    - "Leh" -> "Leh, Ladakh, India"
    - "Indore" -> "Indore, Madhya Pradesh, India"
    - "Bhopal" -> "Bhopal, Madhya Pradesh, India"
    - "Mumbai" -> "Mumbai, Maharashtra, India"
    - "Le Havre" -> "Le Havre, Normandy, France"
    """
    clean_name = (name or "").strip()
    clean_admin = (admin1 or "").strip()
    clean_country = (country or "").strip()
    code = (country_code or "").strip().upper()

    norm_name = clean_name.lower()

    # Rule: Delhi / New Delhi in India -> "Delhi, India"
    if norm_name in ("delhi", "new delhi") and (clean_country == "India" or code == "IN"):
        return "Delhi, India"

    parts = []
    if clean_name:
        parts.append(clean_name)

    # Avoid duplicate or redundant admin1 names
    if clean_admin and clean_admin.lower() != norm_name:
        if not (clean_country == "India" and norm_name in clean_admin.lower()):
            parts.append(clean_admin)

    if clean_country:
        parts.append(clean_country)

    return ", ".join(parts) if parts else clean_name


def select_best_candidate(
    query: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Select the most accurate location candidate using strict exact matching and region awareness."""
    if not results:
        raise CityNotFoundError(f"City '{query}' not found.")

    parts = [p.strip() for p in query.split(",") if p.strip()]
    city_term = parts[0]
    qualifiers = [normalize_name(p) for p in parts[1:]]

    norm_city = normalize_name(city_term)

    # Check for alias in city term
    if norm_city in INDIAN_CITY_ALIASES:
        canonical_alias = INDIAN_CITY_ALIASES[norm_city]
        norm_city = normalize_name(canonical_alias)

    scored_candidates = []
    for cand in results:
        cand_name = normalize_name(cand.get("name"))
        cand_admin = normalize_name(cand.get("admin1"))
        cand_country = normalize_name(cand.get("country"))
        cand_code = (cand.get("country_code") or "").upper()
        pop = cand.get("population") or 0

        # Exact match flag: candidate name matches requested city term or its alias
        is_exact = (cand_name == norm_city)

        # Qualifier match flag (e.g., matching state or country if provided)
        qualifier_match = True
        if qualifiers:
            qualifier_match = any(
                q in cand_admin or q in cand_country or q == cand_code.lower()
                for q in qualifiers
            )

        scored_candidates.append({
            "candidate": cand,
            "is_exact": is_exact,
            "qualifier_match": qualifier_match,
            "population": pop,
            "is_indian": (cand_code == "IN" or cand_country == "india"),
        })

    # If qualifiers were specified by user, prioritize candidates matching qualifiers
    if qualifiers:
        filtered = [c for c in scored_candidates if c["qualifier_match"]]
        if filtered:
            scored_candidates = filtered

    # 1. Evaluate Exact Name Matches First
    exact_candidates = [c for c in scored_candidates if c["is_exact"]]

    if exact_candidates:
        # Check if any exact candidate is in India
        indian_exact = [c for c in exact_candidates if c["is_indian"]]
        if indian_exact:
            # Sort Indian exact matches by population descending
            indian_exact.sort(key=lambda x: x["population"], reverse=True)
            return indian_exact[0]["candidate"]

        # Check for ambiguity among exact matches when no qualifier was provided:
        if not qualifiers and len(exact_candidates) > 1:
            significant = [c for c in exact_candidates if c["population"] > 10000]
            if len(significant) > 1:
                sig_sorted = sorted(significant, key=lambda x: x["population"], reverse=True)
                top_pop = sig_sorted[0]["population"]
                second_pop = sig_sorted[1]["population"]
                c1 = sig_sorted[0]["candidate"]
                c2 = sig_sorted[1]["candidate"]
                distinct_loc = (
                    c1.get("country_code") != c2.get("country_code") or
                    c1.get("admin1") != c2.get("admin1")
                )
                if distinct_loc and second_pop > (top_pop * 0.3):
                    hint_loc = c1.get("admin1") or c1.get("country")
                    raise AmbiguousLocationError(
                        f"Multiple locations match '{city_term}'. Please specify the country or region (e.g. '{city_term}, {hint_loc}')."
                    )

        # Return highest population exact match
        exact_candidates.sort(key=lambda x: x["population"], reverse=True)
        return exact_candidates[0]["candidate"]

    # 2. No Exact Name Match:
    # If user did not provide qualifiers and multiple fuzzy candidates exist across different countries
    if not qualifiers and len(scored_candidates) > 1:
        c1 = scored_candidates[0]["candidate"]
        c2 = scored_candidates[1]["candidate"]
        distinct_country = c1.get("country_code") != c2.get("country_code")
        if distinct_country:
            raise AmbiguousLocationError(
                f"Multiple locations match '{city_term}'. Please specify the country or region (e.g. '{city_term}, {c1.get('country')}')."
            )

    # Return top candidate
    return scored_candidates[0]["candidate"]


class LocationResolver:
    """Centralized, country/region-aware location resolution service."""

    def __init__(
        self,
        geocoding_base_url: str = "https://geocoding-api.open-meteo.com/v1/search",
        timeout: float = 10.0,
    ) -> None:
        self.geocoding_base_url = geocoding_base_url
        self.timeout = timeout
        self._cache: Dict[str, Dict[str, Any]] = {}

    def resolve_location(self, city: str) -> Dict[str, Any]:
        """Convert a city/location name into canonical coordinates and formatted address.

        Args:
            city: City or location string (e.g. 'Leh', 'Indore', 'Delhi', 'Le Havre', 'Bombay')

        Returns:
            Dict containing name, city, latitude, longitude, formatted_address, and timezone.

        Raises:
            CityNotFoundError: If city cannot be found.
            AmbiguousLocationError: If query matches multiple competing locations without qualification.
            WeatherTimeoutError / WeatherServiceUnavailableError on network errors.
        """
        if not city or not city.strip():
            raise CityNotFoundError("City name cannot be empty.")

        clean_query = city.strip()
        cache_key = normalize_name(clean_query)

        # Check in-memory cache
        if cache_key in self._cache:
            logger.debug("Location cache hit for '%s'", clean_query)
            return self._cache[cache_key]

        # Check aliases
        search_term = clean_query
        if cache_key in INDIAN_CITY_ALIASES:
            canonical_alias = INDIAN_CITY_ALIASES[cache_key]
            logger.info("Resolving alias '%s' -> '%s'", clean_query, canonical_alias)
            search_term = canonical_alias

        params = {
            "name": search_term,
            "count": 20,
            "language": "en",
            "format": "json",
        }

        logger.debug("Resolving location via Geocoding API for '%s'", search_term)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.geocoding_base_url, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Geocoding request timed out for city: %s", clean_query)
            if cache_key in WELL_KNOWN_INDIAN_CITIES:
                logger.info("Falling back to pre-configured coordinates for '%s'", clean_query)
                return WELL_KNOWN_INDIAN_CITIES[cache_key]
            raise WeatherTimeoutError("Geocoding request timed out.") from exc
        except httpx.RequestError as exc:
            logger.error("Geocoding network error: %s", str(exc))
            if cache_key in WELL_KNOWN_INDIAN_CITIES:
                logger.info("Falling back to pre-configured coordinates for '%s'", clean_query)
                return WELL_KNOWN_INDIAN_CITIES[cache_key]
            raise WeatherServiceUnavailableError("Unable to connect to location service.") from exc

        if response.status_code == 429:
            logger.error("Geocoding API rate limit hit")
            if cache_key in WELL_KNOWN_INDIAN_CITIES:
                return WELL_KNOWN_INDIAN_CITIES[cache_key]
            raise WeatherRateLimitError("Location service rate limit exceeded.")

        if response.status_code >= 500:
            logger.error("Geocoding API service unavailable (status %s)", response.status_code)
            if cache_key in WELL_KNOWN_INDIAN_CITIES:
                return WELL_KNOWN_INDIAN_CITIES[cache_key]
            raise WeatherServiceUnavailableError("Location service is temporarily unavailable.")

        if response.status_code != 200:
            logger.error("Geocoding API returned status %s", response.status_code)
            raise WeatherServiceUnavailableError("Location service returned an error.")

        try:
            payload = response.json()
        except Exception as exc:
            logger.error("Failed to parse Geocoding API JSON response")
            raise WeatherResponseParsingError("Invalid response format from location service.") from exc

        results = payload.get("results")
        if not results:
            if cache_key in WELL_KNOWN_INDIAN_CITIES:
                return WELL_KNOWN_INDIAN_CITIES[cache_key]
            logger.warning("City '%s' not found via Geocoding API", clean_query)
            raise CityNotFoundError(f"City '{clean_query}' not found.")

        # Smart candidate selection
        best_candidate = select_best_candidate(search_term, results)

        candidate_name = best_candidate.get("name", search_term)
        admin1 = best_candidate.get("admin1")
        country = best_candidate.get("country")
        country_code = best_candidate.get("country_code")

        formatted_address = format_location_address(
            name=candidate_name,
            admin1=admin1,
            country=country,
            country_code=country_code,
        )

        resolved = {
            "city": candidate_name,
            "name": candidate_name,
            "latitude": float(best_candidate["latitude"]),
            "longitude": float(best_candidate["longitude"]),
            "timezone": best_candidate.get("timezone", "Asia/Kolkata" if country_code == "IN" else "UTC"),
            "formatted_address": formatted_address,
            "admin1": admin1,
            "country": country,
            "country_code": country_code,
        }

        self._cache[cache_key] = resolved
        return resolved


# Global singleton instance
location_resolver = LocationResolver()
