# Placeholder async DB init; swap to Postgres later.
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.settings import get_settings

_engine = None
_sessionmaker = None

async def init_db():
    global _engine, _sessionmaker
    url = get_settings().database_url
    # Support both sqlite+aiosqlite and postgresql+asyncpg
    _engine = create_async_engine(url, echo=False, future=True)
    _sessionmaker = sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    if _sessionmaker is None:
        await init_db()
    return _sessionmaker()
