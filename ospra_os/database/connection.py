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
from functools import lru_cache
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Get database URL from environment (PostgreSQL required)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required for PostgreSQL connection. "
        "Set it to your PostgreSQL connection string (e.g., postgresql://user:pass@host:5432/dbname)"
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

    # Handle Render's postgres:// URL format (needs postgresql://)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Verify it's a PostgreSQL URL
    if not url.startswith("postgresql://"):
        raise ValueError(
            f"Invalid database URL. PostgreSQL required, got: {url[:20]}... "
            "Expected format: postgresql://user:pass@host:5432/dbname"
        )

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


def get_db(database_url: str = None) -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            pass
    """
    session = get_session(database_url)
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
