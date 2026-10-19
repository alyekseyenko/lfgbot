from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.events import EventBus
from app.db.models import CompletionKind, Lobby, LobbyCompletion
from app.services.gamification import (
    LEVEL_AGENTE,
    LEVEL_NONE,
    LEVEL_RADIANTE,
    LEVEL_RECRUTA,
    level_from_counts,
    level_progress_line,
    next_level_hint,
    profile_stats,
    progress_bar,
    recent_completions,
    record_lobby_completions,
    week_start_for_date,
    weekly_top_hosts,
)
from app.services.lobbies import (
    close_lobby,
    create_lobby,
    expire_due_lobbies,
    join_lobby,
    kick_member_as_host,
    leave_lobby,
)
from app.services.users import upsert_user


@pytest.fixture
def gamification_on(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        gamification_enabled=True,
        completion_min_seconds=180,
    )
    monkeypatch.setattr("app.services.gamification.get_settings", lambda: settings)
    return settings


async def _full_lobby(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    host_id: int = 9001,
    slots: int = 1,
    player_ids: list[int] | None = None,
    age_minutes: int = 10,
) -> tuple:
    player_ids = player_ids or [9002]
    await upsert_user(session, host_id, f"Host{host_id}")
    for pid in player_ids:
        await upsert_user(session, pid, f"P{pid}")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, host_id, f"Host{host_id}")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=slots,
            party_code="X00001",
            expires_in=timedelta(minutes=30),
        )
        lobby.created_at = datetime.now(UTC) - timedelta(minutes=age_minutes)
        for pid in player_ids:
            user = await upsert_user(session, pid, f"P{pid}")
            member = await join_lobby(session, event_bus, lobby_id=lobby.id, user=user)
            member.joined_at = datetime.now(UTC) - timedelta(minutes=age_minutes)
    return lobby


def test_level_thresholds() -> None:
    assert level_from_counts(0, 0) == LEVEL_NONE
    assert level_from_counts(0, 1) == LEVEL_RECRUTA
    assert level_from_counts(3, 3) == LEVEL_AGENTE
    assert level_from_counts(0, 5) == LEVEL_AGENTE
    assert level_from_counts(2, 20) == LEVEL_RADIANTE


def test_next_level_hint_radiante() -> None:
    assert "máximo" in next_level_hint(5, 25)


def test_progress_bar_bounds() -> None:
    assert progress_bar(0, 5) == "▱▱▱▱▱▱▱▱▱▱"
    assert progress_bar(5, 5).startswith("▰")


def test_level_progress_line_recruta() -> None:
    line = level_progress_line(0, 0)
    assert "Recruta" in line


def test_format_progress_block_agente_path() -> None:
    from app.bot.profile_embed import format_progress_block

    block = format_progress_block(1, 2)
    assert "Agente" in block
    assert "Host" in block


def test_week_start_monday() -> None:
    wednesday = date(2026, 10, 14)
    assert week_start_for_date(wednesday) == date(2026, 10, 12)


@pytest.mark.asyncio
async def test_full_close_awards_host_and_players(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, slots=1, player_ids=[9002])

    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 2

    await session.commit()
    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 2


@pytest.mark.asyncio
async def test_partial_lobby_no_award(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    await upsert_user(session, 8001, "H")
    await session.commit()
    async with session.begin():
        host = await upsert_user(session, 8001, "H")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )
        lobby.created_at = datetime.now(UTC) - timedelta(minutes=10)

    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 0


@pytest.mark.asyncio
async def test_expire_full_awards(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus)
    now = datetime.now(UTC)

    async with session.begin():
        lobby_row = await session.get(Lobby, lobby.id)
        assert lobby_row is not None
        lobby_row.expires_at = now - timedelta(seconds=1)

    async with session.begin():
        expired = await expire_due_lobbies(session, event_bus, now=now)
    assert len(expired) == 1

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 2


@pytest.mark.asyncio
async def test_expire_incomplete_no_award(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    await upsert_user(session, 7001, "H")
    await session.commit()
    now = datetime.now(UTC)
    async with session.begin():
        host = await upsert_user(session, 7001, "H")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(seconds=1),
        )
        lobby.created_at = now - timedelta(minutes=10)
        lobby.expires_at = now - timedelta(seconds=1)

    async with session.begin():
        await expire_due_lobbies(session, event_bus, now=now)

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 0


@pytest.mark.asyncio
async def test_player_too_short_stay_not_awarded(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, age_minutes=10)
    async with session.begin():
        from app.db.models import LobbyMember

        result = await session.execute(select(LobbyMember).where(LobbyMember.lobby_id == lobby.id))
        member = result.scalar_one()
        member.joined_at = datetime.now(UTC) - timedelta(seconds=30)

    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    host_rows = await session.execute(
        select(LobbyCompletion).where(LobbyCompletion.kind == CompletionKind.host.value)
    )
    player_rows = await session.execute(
        select(LobbyCompletion).where(LobbyCompletion.kind == CompletionKind.player.value)
    )
    assert len(list(host_rows.scalars())) == 1
    assert len(list(player_rows.scalars())) == 0


@pytest.mark.asyncio
async def test_lobby_too_young_no_award(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, age_minutes=0)
    async with session.begin():
        lobby_row = await session.get(Lobby, lobby.id)
        assert lobby_row is not None
        lobby_row.created_at = datetime.now(UTC) - timedelta(seconds=30)

    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    result = await session.execute(select(func.count()).select_from(LobbyCompletion))
    assert int(result.scalar_one()) == 0


@pytest.mark.asyncio
async def test_kick_counts_in_profile(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, host_id=6001, player_ids=[6002])
    async with session.begin():
        await kick_member_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=6001,
            target_user_id=6002,
        )

    stats = await profile_stats(session, 6002)
    assert stats.kicks_received == 1


@pytest.mark.asyncio
async def test_early_leave_no_player_credit(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, host_id=5001, player_ids=[5002])
    async with session.begin():
        user = await upsert_user(session, 5002, "P")
        await leave_lobby(session, event_bus, lobby_id=lobby.id, user=user, reason="left")

    await upsert_user(session, 5003, "P3")
    await session.commit()
    async with session.begin():
        user3 = await upsert_user(session, 5003, "P3")
        m = await join_lobby(session, event_bus, lobby_id=lobby.id, user=user3)
        m.joined_at = datetime.now(UTC) - timedelta(minutes=10)

    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    result = await session.execute(select(LobbyCompletion).where(LobbyCompletion.user_id == 5002))
    assert list(result.scalars()) == []


@pytest.mark.asyncio
async def test_weekly_top_respects_week_window(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, host_id=4001, player_ids=[4002])
    award_time = datetime.now(UTC) - timedelta(minutes=5)
    week = week_start_for_date(award_time.date())

    async with session.begin():
        await record_lobby_completions(session, lobby, now=award_time)

    async with session.begin():
        top = await weekly_top_hosts(session, week)
    assert len(top) == 1
    assert top[0].user_id == 4001

    other_week = week - timedelta(days=7)
    async with session.begin():
        empty = await weekly_top_hosts(session, other_week)
    assert empty == []


@pytest.mark.asyncio
async def test_profile_stats_after_completion(
    session: AsyncSession, event_bus: EventBus, gamification_on: Settings
) -> None:
    lobby = await _full_lobby(session, event_bus, host_id=3001, player_ids=[3002])
    async with session.begin():
        await close_lobby(session, event_bus, lobby_id=lobby.id)

    host_stats = await profile_stats(session, 3001)
    player_stats = await profile_stats(session, 3002)
    assert host_stats.level == LEVEL_RECRUTA
    assert host_stats.host_completions == 1
    assert player_stats.player_completions == 1
    assert player_stats.total_completions == 1

    recent_host = await recent_completions(session, 3001)
    assert len(recent_host) == 1
    assert recent_host[0].kind == "host"
    assert recent_host[0].mode == "Unrated"
