import asyncio
import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.domain_event_session import set_domain_event_bus
from app.core.events import EventBus
from app.db.base import Base
from app.db import models  # noqa: F401


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture(autouse=True)
def _wire_domain_event_bus(event_bus: EventBus) -> None:
    set_domain_event_bus(event_bus)


@pytest.fixture(autouse=True)
async def _drain_domain_event_tasks() -> AsyncIterator[None]:
    yield
    await asyncio.sleep(0.05)


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
