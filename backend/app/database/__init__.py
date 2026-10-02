"""Database layer: Database engine, session management, and migrations.

Architecture Rule:
- Future branch: Database connections and session lifecycle management.
"""

from app.database.session import Base, SessionLocal, engine, get_db, init_db

__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db"]
