"""
Database Connection Manager
===========================
Handles SQLite (local dev) and PostgreSQL (production) seamlessly.

Usage:
    from ospra_os.database.connection import get_engine, get_session, get_db

    # For manual session management
    session = get_session()
    
    # For FastAPI dependency injection
    @app.get("/endpoint")
    def endpoint(db: Session = Depends(get_db)):
        pass
"""

import os
import sys
from functools import lru_cache
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Get database URL from environment (PostgreSQL required for production)
# Note: This is read at import time but validated at runtime in get_engine()
DATABASE_URL = os.getenv("DATABASE_URL")

# Check if we're in test mode
def is_test_mode() -> bool:
    """Detect if running in test environment."""
    return (
        "pytest" in sys.modules or
        os.getenv("TESTING") == "true" or
        os.getenv("ENV") == "test"
    )


def get_pool_args() -> dict:
    """
    Get PostgreSQL connection pool configuration.

    Returns optimized pool settings for production PostgreSQL usage.
    """
    return {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": 3600,   # Recycle connections after 1 hour
    }


@lru_cache(maxsize=1)
def get_engine(database_url: str = None):
    """
    Create PostgreSQL SQLAlchemy engine with optimized connection pooling.

    Cached to ensure single engine instance across the application.
    """
    url = database_url or DATABASE_URL

    # In test mode, use SQLite in-memory database if no DATABASE_URL provided
    if not url and is_test_mode():
        url = "sqlite:///:memory:"

    # In local development (no DATABASE_URL set), use SQLite file database
    if not url:
        print("[INFO] DATABASE_URL not set - using SQLite for local development")
        url = "sqlite:///./data/ospra_local.db"

    # Handle different PostgreSQL URL formats
    if url.startswith("postgres://"):
        # Render's default format - convert to postgresql://
        url = url.replace("postgres://", "postgresql://", 1)

    # Remove any existing driver specification (like +asyncpg, +psycopg2, etc.)
    if url.startswith("postgresql+"):
        # Extract the base URL without the driver (e.g., postgresql+asyncpg:// -> postgresql://)
        driver_end = url.find("://")
        if driver_end > 0:
            url = "postgresql://" + url[driver_end + 3:]

    # Verify it's a PostgreSQL URL (allow SQLite in test mode or local dev)
    if not url.startswith("postgresql://"):
        # Allow SQLite in test environments OR local development (when DATABASE_URL not set)
        if (is_test_mode() or DATABASE_URL is None) and url.startswith("sqlite:///"):
            # SQLite doesn't need connection pooling
            engine = create_engine(
                url,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
                connect_args={"check_same_thread": False}
            )
            return engine

        raise ValueError(
            f"Invalid database URL. PostgreSQL required, got: {url[:20]}... "
            "Expected format: postgresql://user:pass@host:5432/dbname"
        )

    # Force psycopg2 driver (synchronous) to avoid MissingGreenlet errors
    # This ensures compatibility with synchronous FastAPI startup events
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(
        url,
        **get_pool_args(),
        echo=os.getenv("SQL_ECHO", "false").lower() == "true"
    )

    return engine


def get_session_factory(database_url: str = None):
    """Create session factory bound to engine."""
    engine = get_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session(database_url: str = None) -> Session:
    """
    Create a new database session.
    
    Remember to close when done:
        session = get_session()
        try:
            # do stuff
        finally:
            session.close()
    """
    SessionLocal = get_session_factory(database_url)
    return SessionLocal()


@contextmanager
def get_session_context(database_url: str = None) -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_session_context() as session:
            session.query(...)
    """
    session = get_session(database_url)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            pass
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def init_database(database_url: str = None):
    """
    Initialize PostgreSQL database - create all tables.

    Call this on app startup.
    """
    from ospra_os.database.base import Base

    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)

    print(f"[SUCCESS] PostgreSQL database initialized")
    print(f"   URL: {str(engine.url).split('@')[-1]}")  # Hide credentials
    print(f"   Tables: {len(Base.metadata.tables)}")

    return engine


def check_database_connection(database_url: str = None) -> dict:
    """
    Check PostgreSQL database connectivity and return status.

    Useful for health checks.
    """
    try:
        engine = get_engine(database_url)

        from sqlalchemy import text

        with engine.connect() as conn:
            # Simple query to verify connection
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        return {
            "status": "healthy",
            "database_type": "postgresql",
            "url_masked": str(engine.url).split("@")[-1] if "@" in str(engine.url) else str(engine.url)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# Backwards compatibility - alias for existing code
def get_multi_store_session(database_url: str = None) -> Session:
    """Backwards compatible alias for get_session."""
    return get_session(database_url)


def init_multi_store_db(database_url: str = None):
    """Backwards compatible alias for init_database."""
    return init_database(database_url)
