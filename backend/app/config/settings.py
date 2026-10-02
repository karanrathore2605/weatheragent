"""Application settings and environment configuration management."""

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production-grade application configuration.
    
    Reads from environment variables and an optional .env file.
    No secrets or API keys are hard-coded.
    """

    app_name: str = "Weather Forecast Agent API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS configuration
    cors_origins: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Logging configuration
    log_level: str = "INFO"

    # Weather API configuration
    google_weather_api_key: str = ""
    weather_api_timeout: float = 10.0
    weather_api_base_url: str = "https://weather.googleapis.com/v1"
    google_geocoding_base_url: str = "https://maps.googleapis.com/maps/api/geocode/json"

    # Database configuration
    database_url: str = "sqlite:///./weatheragent.db"

    # Statistics configuration
    min_statistics_coverage: float = 70.0

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Support comma-separated strings or JSON arrays for CORS origins."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parent.parent.parent / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()


# Default settings instance for direct access
settings = get_settings()
