"""Async SQLAlchemy engine, session factory, and the `get_db` request dependency.

This is the single place the application opens database connections. The engine
is configured to survive database restarts on its own: `pool_pre_ping` validates
each pooled connection with a lightweight liveness check before handing it to a
request (transparently discarding sockets killed by a Postgres restart, failover,
or maintenance), and `pool_recycle` proactively retires connections older than the
recycle window so we never hand out a connection the server has already timed out.
Without these, a brief DB blip leaves the pool full of dead sockets and every
request fails with 500s until the process is restarted by hand.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_settings = get_settings()

# Recycle connections after 30 minutes — comfortably under typical idle/server
# timeouts, so a pooled connection is never the stale one a request trips over.
_POOL_RECYCLE_SECONDS = 1800

engine = create_async_engine(
    _settings.async_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=_POOL_RECYCLE_SECONDS,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
