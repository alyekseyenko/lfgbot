import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db import models  # noqa: F401


def _test_database_url() -> str:
    default = "postgresql+asyncpg://lfg:lfg@postgres:5432/lfg_test"
    url = os.environ.get("TEST_DATABASE_URL", default)
    if url.endswith("/lfg") and "TEST_DATABASE_URL" not in os.environ:
        url = url.replace("/lfg", "/lfg_test", 1)
    return url


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    url = _test_database_url()
    eng = create_async_engine(url, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as sess:
        yield sess
