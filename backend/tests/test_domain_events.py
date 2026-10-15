from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventBus, EventType
from app.services.lobbies import create_lobby
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_domain_events_published_after_commit(
    session: AsyncSession, event_bus: EventBus
) -> None:
    received: list[DomainEvent] = []

    async def listener(event: DomainEvent) -> None:
        received.append(event)

    event_bus.subscribe(listener)

    async with session.begin():
        host = await upsert_user(session, 9001, "Host9001")
        await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )

    await asyncio.sleep(0.06)
    assert len(received) == 1
    assert received[0].type == EventType.lobby_created


@pytest.mark.asyncio
async def test_domain_events_discarded_on_rollback(
    session: AsyncSession, event_bus: EventBus
) -> None:
    received: list[DomainEvent] = []

    async def listener(event: DomainEvent) -> None:
        received.append(event)

    event_bus.subscribe(listener)

    try:
        async with session.begin():
            host = await upsert_user(session, 9002, "Host9002")
            await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=2,
                party_code=None,
                expires_in=timedelta(minutes=30),
            )
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    assert received == []
