"""Database engine, session management, and lifecycle handling.

Architecture Rules:
- Environment-based configuration (SQLite, PostgreSQL, etc.).
- Safe session lifecycle management with FastAPI dependency injection.
- Tables auto-created on application startup via init_db().
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Configure connect_args based on DB dialect (e.g. SQLite threading requirements)
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


_db_initialized = False


def init_db() -> None:
    """Initialize database tables according to declared ORM metadata."""
    global _db_initialized
    logger.info("Initializing database tables on engine: %s", settings.database_url.split("///")[-1])
    # Import models so SQLAlchemy metadata registers all ORM tables
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _db_initialized = True


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding an isolated database session."""
    if not _db_initialized:
        init_db()
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

