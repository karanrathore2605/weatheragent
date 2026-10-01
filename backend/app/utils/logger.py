"""Application-level logging setup and utilities."""

import logging
import sys
from typing import Optional

from app.config.settings import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure root logger and application-level logging handlers."""
    level = (log_level or settings.log_level).upper()
    numeric_level = getattr(logging, level, logging.INFO)

    log_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s] "
        "[%(filename)s:%(lineno)d]: %(message)s"
    )

    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Set third-party loggers to reasonable levels
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Obtain a namespaced logger instance."""
    return logging.getLogger(name)
