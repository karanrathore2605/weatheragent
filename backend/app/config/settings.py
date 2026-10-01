"""Application settings and environment configuration management."""

import json
from functools import lru_cache
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
        env_file=".env",
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
