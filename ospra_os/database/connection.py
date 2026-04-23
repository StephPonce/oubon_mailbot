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

    Returns optimized pool settings for production PostgreSQL usage
    with improved transaction error resilience.

    Pool sizing based on expected concurrent users:
    - pool_size: Base connections always maintained (warm pool)
    - max_overflow: Additional connections allowed under load
    - Total max connections = pool_size + max_overflow

    For a SaaS platform with async operations:
    - 20 base + 30 overflow = 50 max connections
    - Handles 100+ concurrent users with proper async patterns
    """
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),  # Configurable via env
        "max_overflow": int(os.getenv("DB_POOL_OVERFLOW", "30")),  # Configurable
        "pool_pre_ping": True,         # Verify connections before use
        "pool_recycle": 1800,          # Recycle connections after 30 min
        "pool_reset_on_return": "rollback",  # Always rollback on connection return
        "pool_timeout": 30,            # Wait up to 30 seconds for a connection
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
    FastAPI dependency for database sessions with proper error handling.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            pass

    Ensures proper transaction cleanup to prevent SQLAlchemy f405 errors
    (stale transactions in connection pool).
    """
    session = get_session()
    try:
        yield session
    except Exception:
        # Explicitly rollback on error to prevent stale transactions
        session.rollback()
        raise
    finally:
        session.close()


# Critical tables that MUST exist for the app to function
CRITICAL_TABLES = ['users', 'stores', 'products', 'user_settings']


def _import_all_models():
    """
    Import all model files to register them with SQLAlchemy Base.
    
    This must be called before any create_all() or Alembic migration.
    """
    from ospra_os.database.base import Base
    
    model_modules = [
        'user_models',
        'federated_models',
        'core_models',
        'product_models',
        'store_models',
        'testing_models',
        'email_models',
        'action_models',
        'advertising_models',
        
        'performance_models',
        'whitelabel_models',
        'template_models',
        'amazon_models',
        'aliexpress_tokens',
        'cached_products',
        'enhanced_image_cache',  # Enhanced image caching for Stability AI
    ]
    
    imported = 0
    for module_name in model_modules:
        try:
            __import__(f'ospra_os.database.{module_name}')
            imported += 1
        except ImportError:
            pass  # Optional module
        except Exception as e:
            print(f"[DB INIT]   ✗ {module_name}: {e}")
    
    print(f"[DB INIT] Imported {imported} model modules ({len(Base.metadata.tables)} tables registered)")
    return Base


def _run_alembic_migrations():
    """
    Run Alembic migrations to upgrade database to latest version.
    
    Returns True if successful, False if Alembic unavailable or failed.
    """
    try:
        from alembic.config import Config
        from alembic import command
        import os
        
        # Find alembic.ini relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        alembic_ini = os.path.join(project_root, 'alembic.ini')
        
        if not os.path.exists(alembic_ini):
            print(f"[DB INIT] alembic.ini not found at {alembic_ini}")
            return False
        
        # Check if any migrations exist
        versions_dir = os.path.join(project_root, 'alembic', 'versions')
        if not os.path.exists(versions_dir):
            print("[DB INIT] No alembic/versions directory found")
            return False
            
        migrations = [f for f in os.listdir(versions_dir) if f.endswith('.py') and not f.startswith('__')]
        if not migrations:
            print("[DB INIT] No Alembic migrations found - using create_all() fallback")
            return False
        
        print(f"[DB INIT] Running Alembic migrations ({len(migrations)} found)...")
        
        alembic_cfg = Config(alembic_ini)
        command.upgrade(alembic_cfg, "head")
        
        print("[DB INIT] ✓ Alembic migrations complete")
        return True
        
    except ImportError:
        print("[DB INIT] Alembic not installed - using create_all() fallback")
        return False
    except Exception as e:
        print(f"[DB INIT] Alembic migration failed: {e}")
        return False


def verify_database_schema(engine=None) -> dict:
    """
    Verify that critical database tables exist.
    
    Returns dict with status and any missing tables.
    Use this for health checks and startup validation.
    """
    if engine is None:
        engine = get_engine()
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    missing = [t for t in CRITICAL_TABLES if t not in existing_tables]
    
    return {
        'status': 'healthy' if not missing else 'degraded',
        'total_tables': len(existing_tables),
        'critical_tables': CRITICAL_TABLES,
        'missing_tables': missing,
        'all_present': len(missing) == 0
    }


def init_database(database_url: str = None):
    """
    Initialize database schema on app startup.
    
    Strategy:
    1. For PostgreSQL: Try Alembic migrations first, fall back to create_all()
    2. For SQLite: Use create_all() directly (local dev)
    3. Always verify critical tables exist after initialization
    
    Raises RuntimeError if critical tables are missing after init.
    """
    print("[DB INIT] Starting database initialization...")
    
    try:
        # Import all models first
        Base = _import_all_models()
        
        # Get engine
        engine = get_engine(database_url)
        db_type = 'postgresql' if 'postgresql' in str(engine.url) else 'sqlite'
        print(f"[DB INIT] Database type: {db_type}")
        
        # Check existing tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f"[DB INIT] Existing tables: {len(existing_tables)}")
        
        # Check if schema already exists
        schema_check = verify_database_schema(engine)
        if schema_check['all_present']:
            print(f"[DB INIT] ✓ All {len(CRITICAL_TABLES)} critical tables present - schema OK")
            return engine
        
        # Schema missing or incomplete - need to create
        print(f"[DB INIT] Missing tables: {schema_check['missing_tables']}")
        
        # Try Alembic first (PostgreSQL production)
        if db_type == 'postgresql':
            if _run_alembic_migrations():
                # Verify after Alembic
                schema_check = verify_database_schema(engine)
                if schema_check['all_present']:
                    print("[DB INIT] ✓ Schema ready via Alembic")
                    return engine
        
        # Fall back to create_all() (SQLite or Alembic failed/unavailable)
        print("[DB INIT] Using SQLAlchemy create_all()...")
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as create_error:
            print(f"[DB INIT] create_all() failed: {create_error}")
            
            # For empty databases, try dropping everything first
            if len(existing_tables) > 0:
                print("[DB INIT] Partial schema detected - attempting clean slate...")
                from sqlalchemy import text
                with engine.connect() as conn:
                    for table in existing_tables:
                        try:
                            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                        except Exception as e:
                            logger.warning(f"Failed to drop table {table}: {e}")
                    conn.commit()
                
                # Retry create_all
                Base.metadata.create_all(bind=engine)
        
        # Final verification
        inspector = inspect(engine)
        final_tables = inspector.get_table_names()
        schema_check = verify_database_schema(engine)
        
        print(f"[DB INIT] Final table count: {len(final_tables)}")
        
        if not schema_check['all_present']:
            error_msg = f"CRITICAL: Missing tables after init: {schema_check['missing_tables']}"
            print(f"[DB INIT] ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        print("[DB INIT] ✓ Database initialization complete")
        print(f"[DB INIT]   Tables: {len(final_tables)}")
        print(f"[DB INIT]   Critical tables: All present")
        
        return engine
        
    except Exception as e:
        import traceback
        import logging
        db_logger = logging.getLogger(__name__)
        # Log full traceback to logger (not stdout) for debugging
        db_logger.error(f"[DB INIT] ERROR: {e}\nTraceback: {traceback.format_exc()}")
        print(f"[DB INIT] ERROR: Database initialization failed. Check logs for details.")
        raise


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


# ============================================================================
# MODULE-LEVEL EXPORTS
# ============================================================================
# Create module-level engine and SessionLocal for backward compatibility
# These are used by scripts and modules that need to:
# 1. Create tables: Base.metadata.create_all(bind=engine)
# 2. Create sessions: db = SessionLocal()

engine = get_engine()
SessionLocal = get_session_factory()


# ============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# ============================================================================

# Backwards compatibility - alias for existing code
def get_multi_store_session(database_url: str = None) -> Session:
    """Backwards compatible alias for get_session."""
    return get_session(database_url)


def init_multi_store_db(database_url: str = None):
    """Backwards compatible alias for init_database."""
    return init_database(database_url)
