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

import logging
import os
import sys
from functools import lru_cache
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

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
    # NOTE on sizing: pool_size + max_overflow must stay UNDER the database's
    # max_connections. Neon/Render Postgres often caps well below 50, and with
    # sync psycopg2 each web worker holds its own pool — so the effective total
    # is (pool_size + max_overflow) x web-worker-count. Tune DB_POOL_SIZE /
    # DB_POOL_OVERFLOW down (e.g. 10 / 10) if you see "too many connections".
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),  # Configurable via env
        "max_overflow": int(os.getenv("DB_POOL_OVERFLOW", "30")),  # Configurable
        "pool_pre_ping": True,         # Verify connections before use
        "pool_recycle": 1800,          # Recycle connections after 30 min
        "pool_reset_on_return": "rollback",  # Always rollback on connection return
        # Fail fast instead of hanging: a request that can't get a connection
        # in 10s should error rather than block for 30s and pile up (the old
        # 30s value turned a brief pool contention spike into a cascade).
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
    }


@lru_cache(maxsize=1)
def get_engine(database_url: str = None):
    """
    Create PostgreSQL SQLAlchemy engine with optimized connection pooling.

    Cached to ensure single engine instance across the application.
    """
    url = database_url or DATABASE_URL

    # ``make dev-local`` sets this to force SQLite regardless of what the
    # .env file has configured. Without this flag, ``load_dotenv(override=True)``
    # in main.py would clobber the empty ``DATABASE_URL`` we set on the
    # command line and we'd be back to hitting the remote DB.
    if os.getenv("OSPRA_FORCE_LOCAL_SQLITE") == "1":
        url = "sqlite:///./data/ospra_local.db"
        print("[INFO] OSPRA_FORCE_LOCAL_SQLITE=1 — using local SQLite (overrides .env)")

    # In test mode, use SQLite in-memory database if no DATABASE_URL provided
    if not url and is_test_mode():
        url = "sqlite:///:memory:"

    # In local development (no DATABASE_URL set), use SQLite file database.
    if not url:
        # T101: in production, a missing DATABASE_URL previously fell back to an
        # ephemeral SQLite file that Render wipes on every deploy/restart — real
        # customer data would silently vanish with no alert. Fail fast instead so
        # the deploy goes red and the misconfiguration is obvious, never silent.
        _prod = (
            os.getenv("ENVIRONMENT", "").lower() == "production"
            or os.getenv("RENDER") is not None
        )
        if _prod:
            raise RuntimeError(
                "DATABASE_URL is not set in a production environment. Refusing to "
                "fall back to ephemeral SQLite (data would be lost on restart). "
                "Set DATABASE_URL to the managed Postgres connection string."
            )
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
        'tiktok_tokens',  # T161: was never imported here, so its table never registered
        'cached_products',
        'enhanced_image_cache',  # Enhanced image caching for Stability AI
        'fulfillment_models',  # T16: idempotency records for auto-fulfillment
        'webhook_event_models',  # T27: payment-webhook replay protection
        'product_timeseries',  # Moat P1: daily units-sold snapshots
        'product_comments',  # Moat P2: per-comment engagement (organic-vs-seeded)
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


def _run_alembic_migrations(strict: bool = False):
    """
    Run Alembic migrations to upgrade database to latest version.

    Returns True if successful, False if Alembic unavailable or failed.
    With ``strict=True`` (PostgreSQL production), any failure RAISES
    instead — a half-migrated schema must red the deploy, not silently
    fall through to create_all (which papers over missing columns; that
    fallback is how prod drifted 34 columns behind the models).
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
            if strict:
                raise RuntimeError(f"alembic.ini not found at {alembic_ini}")
            return False
        
        # Check if any migrations exist
        versions_dir = os.path.join(project_root, 'alembic', 'versions')
        if not os.path.exists(versions_dir):
            print("[DB INIT] No alembic/versions directory found")
            return False
            
        migrations = [f for f in os.listdir(versions_dir) if f.endswith('.py') and not f.startswith('__')]
        if not migrations:
            print("[DB INIT] No Alembic migrations found - using create_all() fallback")
            if strict:
                raise RuntimeError("No Alembic migrations found but required in production")
            return False
        
        print(f"[DB INIT] Running Alembic migrations ({len(migrations)} found)...")
        
        alembic_cfg = Config(alembic_ini)
        command.upgrade(alembic_cfg, "head")
        
        print("[DB INIT] ✓ Alembic migrations complete")
        return True
        
    except ImportError:
        print("[DB INIT] Alembic not installed - using create_all() fallback")
        if strict:
            raise RuntimeError("Alembic not installed but required in production")
        return False
    except Exception as e:
        print(f"[DB INIT] Alembic migration failed: {e}")
        if strict:
            raise
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
    1. PostgreSQL (production): ALWAYS run Alembic upgrade head (strict —
       failure raises), then the idempotent create_all backfill for
       model-only tables, then a strict drift guard that raises if any
       model column is absent from the live DB. There is NO create_all
       fallback on migration failure.
    2. SQLite (local dev / tests): create_all() directly.
    3. Always verify critical tables exist after initialization.

    Raises RuntimeError if migrations fail, critical tables are missing,
    or schema drift is detected (PostgreSQL).
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
        
        if db_type == 'postgresql':
            # Migrations run on EVERY boot, and loudly. The old flow only
            # tried Alembic when a critical table was missing — since prod's
            # 4 critical tables always existed, migrations NEVER ran there,
            # and the on-failure create_all fallback masked it. That's how
            # prod drifted 34 columns behind the models (reconciled by
            # migration 005). strict=True: any migration failure raises and
            # reds the deploy while the previous release keeps serving.
            _run_alembic_migrations(strict=True)

            # Backfill model-only tables. Alembic migrations only manage the
            # tables they define; anything added straight to a model
            # (cached_google_trends, ai_learning_events, ...) still needs the
            # idempotent create_all — it only CREATEs missing tables, never
            # ALTERs or DROPs existing ones.
            try:
                Base.metadata.create_all(bind=engine)
                print("[DB INIT] ✓ Backfilled any missing model-only tables")
            except Exception as backfill_error:
                logger.warning(
                    f"[DB INIT] table backfill failed (non-fatal): {backfill_error}"
                )

            schema_check = verify_database_schema(engine)
            if not schema_check['all_present']:
                raise RuntimeError(
                    f"CRITICAL: Missing tables after init: {schema_check['missing_tables']}"
                )

            # Drift guard: after migrations + backfill, every model column
            # must exist in the live DB. A gap here means a column was added
            # to a model without a migration — the exact class of bug that
            # produced the 34-column drift. Red the deploy instead of
            # shipping a latent 500.
            from ospra_os.database.schema_drift import fail_on_drift
            fail_on_drift(engine)

            print("[DB INIT] ✓ Schema ready via Alembic (drift check clean)")
            return engine

        # ------------------------------------------------------------------
        # SQLite (local dev / tests): create_all builds the full schema from
        # the current models, so migrations aren't needed to stay in sync.
        # ------------------------------------------------------------------
        schema_check = verify_database_schema(engine)
        if schema_check['all_present']:
            print(f"[DB INIT] ✓ All {len(CRITICAL_TABLES)} critical tables present - schema OK")
            try:
                Base.metadata.create_all(bind=engine)
                print("[DB INIT] ✓ Backfilled any missing non-critical tables")
            except Exception as backfill_error:
                logger.warning(
                    f"[DB INIT] non-critical table backfill failed (non-fatal): {backfill_error}"
                )
            return engine

        # Schema missing or incomplete - need to create
        print(f"[DB INIT] Missing tables: {schema_check['missing_tables']}")
        print("[DB INIT] Using SQLAlchemy create_all()...")
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as create_error:
            print(f"[DB INIT] create_all() failed: {create_error}")

            # Audit T100 — DATA-LOSS FIX. The previous code, on a create_all
            # failure against a NON-EMPTY database, ran
            #   DROP TABLE ... CASCADE
            # on every existing table and retried — i.e. it wiped all
            # production data (orders, users, tokens, snapshots) to "fix" a
            # schema error. `create_all` is idempotent (it only CREATEs missing
            # tables), so a failure here means a genuine schema conflict a human
            # must resolve via a migration, NOT something to paper over by
            # deleting data. Never auto-drop. Fail loud so the deploy is red and
            # the DB is untouched.
            if len(existing_tables) > 0:
                raise RuntimeError(
                    "[DB INIT] create_all() failed against a non-empty database. "
                    "Refusing to auto-drop tables (would destroy data). Resolve "
                    "the schema conflict with an Alembic migration and redeploy. "
                    f"Original error: {create_error}"
                ) from create_error
            # Empty DB: safe to surface the real error (no data to lose).
            raise
        
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
        print("[DB INIT]   Critical tables: All present")
        
        return engine
        
    except Exception as e:
        import traceback
        import logging
        db_logger = logging.getLogger(__name__)
        # Log full traceback to logger (not stdout) for debugging
        db_logger.error(f"[DB INIT] ERROR: {e}\nTraceback: {traceback.format_exc()}")
        print("[DB INIT] ERROR: Database initialization failed. Check logs for details.")
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
