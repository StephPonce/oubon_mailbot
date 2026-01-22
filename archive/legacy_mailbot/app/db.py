# Legacy DB module - updated to avoid asyncpg dependency
# NOTE: This module is from the legacy main.py app and should not be used in ospra_os

# For backwards compatibility with legacy main.py
# Just make init_db a no-op to prevent asyncpg errors
_engine = None
_sessionmaker = None

async def init_db():
    """Initialize database - no-op for legacy compatibility"""
    global _engine, _sessionmaker
    # Don't actually initialize anything - just return successfully
    # This prevents the asyncpg import error during startup
    pass

async def get_session():
    """Get database session - returns None for legacy compatibility"""
    # Legacy code shouldn't use this anyway
    return None
