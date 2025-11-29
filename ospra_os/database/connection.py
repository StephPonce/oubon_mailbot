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

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ospra_os.db")


def get_connection_args(url: str) -> dict:
    """
    Get appropriate connection args based on database type.
    
    SQLite: needs check_same_thread=False for FastAPI
    PostgreSQL: no special args needed
    """
    if "sqlite" in url.lower():
        return {
            "check_same_thread": False
        }
    return {}


def get_pool_args(url: str) -> dict:
    """
    Get pool configuration based on database type.
    
    SQLite: use StaticPool for better concurrency
    PostgreSQL: use default connection pooling
    """
    if "sqlite" in url.lower():
        return {
            "poolclass": StaticPool
        }
    return {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True  # Verify connections before use
    }


@lru_cache(maxsize=1)
def get_engine(database_url: str = None):
    """
    Create SQLAlchemy engine with proper configuration.
    
    Cached to ensure single engine instance.
    """
    url = database_url or DATABASE_URL
    
    # Handle Render's postgres:// URL format (needs postgresql://)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(
        url,
        connect_args=get_connection_args(url),
        **get_pool_args(url),
        echo=os.getenv("SQL_ECHO", "false").lower() == "true"
    )
    
    # Enable WAL mode for SQLite (better concurrency)
    if "sqlite" in url.lower():
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    
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
    Initialize database - create all tables.
    
    Call this on app startup.
    """
    from ospra_os.database.multi_store_models import Base
    
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    
    db_type = "PostgreSQL" if "postgresql" in str(engine.url) else "SQLite"
    print(f"✅ Database initialized ({db_type})")
    print(f"   Tables: {len(Base.metadata.tables)}")
    
    return engine


def check_database_connection(database_url: str = None) -> dict:
    """
    Check database connectivity and return status.
    
    Useful for health checks.
    """
    try:
        engine = get_engine(database_url)
        
        from sqlalchemy import text
        
        with engine.connect() as conn:
            # Simple query to verify connection
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        db_type = "postgresql" if "postgresql" in str(engine.url) else "sqlite"
        
        return {
            "status": "healthy",
            "database_type": db_type,
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
