from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.services.errors import SearchBlockedError
from app.services.lobbies import create_lobby, join_lobby, kick_member_as_host, leave_lobby
from app.services.search_cooldown import (
    cooldown_duration_for_daily_count,
    format_search_blocked_until,
)
from app.services.users import upsert_user


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


def test_cooldown_escalation() -> None:
    assert cooldown_duration_for_daily_count(1) == timedelta(minutes=5)
    assert cooldown_duration_for_daily_count(3) == timedelta(minutes=5)
    assert cooldown_duration_for_daily_count(4) == timedelta(minutes=15)
    assert cooldown_duration_for_daily_count(5) == timedelta(hours=12)


def test_format_blocked_message_contains_lisbon() -> None:
    until = datetime(2026, 10, 14, 15, 30, tzinfo=UTC)
    text = format_search_blocked_until(until)
    assert "Lisboa" in text
    assert "15:" in text or "16:" in text


@pytest.mark.asyncio
async def test_private_leave_blocks_search(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 801, "Host", rank="Gold")
    await upsert_user(session, 802, "Guest", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 801, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="ABC123",
            party_code_public=False,
            expires_in=timedelta(minutes=30),
        )
        guest = await upsert_user(session, 802, "Guest", rank="Gold")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)

    async with session.begin():
        guest = await upsert_user(session, 802, "Guest", rank="Gold")
        await leave_lobby(session, event_bus, lobby_id=lobby.id, user=guest, reason="left")

    async with session.begin():
        guest = await upsert_user(session, 802, "Guest", rank="Gold")
        with pytest.raises(SearchBlockedError):
            await create_lobby(
                session,
                event_bus,
                host=guest,
                mode="Unrated",
                slots=1,
                party_code=None,
                expires_in=timedelta(minutes=30),
            )


@pytest.mark.asyncio
async def test_kick_does_not_block_search(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 811, "Host", rank="Gold")
    await upsert_user(session, 812, "Guest", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 811, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="XYZ789",
            party_code_public=False,
            expires_in=timedelta(minutes=30),
        )
        guest = await upsert_user(session, 812, "Guest", rank="Gold")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)

    async with session.begin():
        await kick_member_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=811,
            target_user_id=812,
        )

    async with session.begin():
        guest = await upsert_user(session, 812, "Guest", rank="Gold")
        lobby2 = await create_lobby(
            session,
            event_bus,
            host=guest,
            mode="Unrated",
            slots=1,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )
    assert lobby2.host_id == 812
