"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.config import settings

# Module-level engine — initialized once on startup
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str | None = None, use_null_pool: bool = False) -> AsyncEngine:
    """Create or return the shared async engine.

    Args:
        database_url: Override the DATABASE_URL from settings (used in tests).
        use_null_pool: Use NullPool instead of connection pooling (used in tests
            with SQLite/aiosqlite which do not support concurrent connections).

    Returns:
        The configured AsyncEngine instance.
    """
    global _engine
    if _engine is None:
        url = database_url or settings.database_url
        kwargs: dict = {
            "echo": settings.log_level == "DEBUG",
        }
        if use_null_pool:
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = settings.db_pool_size
            kwargs["max_overflow"] = settings.db_max_overflow
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return (or create) the session factory bound to the given engine.

    Args:
        engine: Engine to bind the factory to. Defaults to the shared engine.

    Returns:
        An async_sessionmaker that produces AsyncSession objects.
    """
    global _session_factory
    if _session_factory is None or engine is not None:
        bound_engine = engine or get_engine()
        _session_factory = async_sessionmaker(
            bind=bound_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Yields:
        An AsyncSession scoped to the current request.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def reset_engine() -> None:
    """Dispose the current engine and clear module state (used in tests)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None
