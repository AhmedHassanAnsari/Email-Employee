"""Async SQLAlchemy engine + session helpers for FastAPI DI.

The engine is created once and bound to the FastAPI app via lifespan; per-request
sessions come from the ``SessionDep`` annotated dependency. Outside FastAPI
(Alembic, the poller, scripts) callers fall back to a module-level engine built
from ``DATABASE_URL``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def async_url(database_url: str | None = None) -> str:
    """Resolve DATABASE_URL and coerce it to the asyncpg driver.

    The env may carry the raw ``postgresql://`` scheme (some tools reject
    ``+asyncpg``); our async engine requires an async driver, so normalise here.
    """
    url = database_url or os.environ["DATABASE_URL"]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql+asyncpg://" + url.split("://", 1)[1]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.split("://", 1)[1]
    return url


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Build an AsyncEngine from ``DATABASE_URL`` (or an override)."""
    url = async_url(database_url)
    return create_async_engine(
        url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
        future=True,
    )


def get_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
        class_=AsyncSession,
    )


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def module_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Session factory for use outside a FastAPI request (poller, Alembic, CLI)."""
    global _engine, _sessionmaker
    if _sessionmaker is None:
        _engine = get_engine()
        _sessionmaker = get_sessionmaker(_engine)
    return _sessionmaker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session bound to the lifespan-owned pool."""
    sm: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "sessionmaker", None
    )
    if sm is None:
        sm = module_sessionmaker()
    async with sm() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
