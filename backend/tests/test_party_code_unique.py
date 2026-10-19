from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import User
from app.services.errors import PartyCodeInUseError, PartyCodeInvalidError
from app.services.lobbies import create_lobby
from app.services.party_code import normalize_party_code


def test_normalize_party_code() -> None:
    assert normalize_party_code("  abc123 ") == "ABC123"
    assert normalize_party_code("") is None
    assert normalize_party_code(None) is None


def test_normalize_party_code_rejects_invalid() -> None:
    with pytest.raises(PartyCodeInvalidError):
        normalize_party_code("ABC12")
    with pytest.raises(PartyCodeInvalidError):
        normalize_party_code("ABCDEF")
    with pytest.raises(PartyCodeInvalidError):
        normalize_party_code("ABC123EXTRA")


@pytest.mark.asyncio
async def test_duplicate_active_party_code_same_guild_rejected(
    session: AsyncSession, event_bus: EventBus
) -> None:
    guild_id = 9001
    host_a = User(discord_id=1, name="a")
    host_b = User(discord_id=2, name="b")
    session.add_all([host_a, host_b])
    await session.flush()

    await create_lobby(
        session,
        event_bus,
        host=host_a,
        mode="Competitivo",
        slots=2,
        party_code="XXXS21",
        expires_in=timedelta(hours=1),
        discord_guild_id=guild_id,
    )
    await session.commit()

    with pytest.raises(PartyCodeInUseError):
        async with session.begin():
            await create_lobby(
                session,
                event_bus,
                host=host_b,
                mode="Competitivo",
                slots=2,
                party_code="xxxs21",
                expires_in=timedelta(hours=1),
                discord_guild_id=guild_id,
            )


@pytest.mark.asyncio
async def test_same_code_different_guilds_allowed(
    session: AsyncSession, event_bus: EventBus
) -> None:
    host_a = User(discord_id=3, name="c")
    host_b = User(discord_id=4, name="d")
    session.add_all([host_a, host_b])
    await session.flush()

    await create_lobby(
        session,
        event_bus,
        host=host_a,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        expires_in=timedelta(hours=1),
        discord_guild_id=1,
    )
    await create_lobby(
        session,
        event_bus,
        host=host_b,
        mode="Unrated",
        slots=3,
        party_code="ABC123",
        expires_in=timedelta(hours=1),
        discord_guild_id=2,
    )


@pytest.mark.asyncio
async def test_no_code_skips_uniqueness(session: AsyncSession, event_bus: EventBus) -> None:
    host = User(discord_id=4, name="d")
    session.add(host)
    await session.flush()

    await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code=None,
        expires_in=timedelta(hours=1),
        discord_guild_id=5,
    )
    await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code=None,
        expires_in=timedelta(hours=1),
        discord_guild_id=5,
    )
