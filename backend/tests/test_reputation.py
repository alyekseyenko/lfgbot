from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import Guild, LobbyReputationPost
from app.services.lobbies import create_lobby, join_lobby
from app.services.reputation import (
    ReputationLeaderboardEntry,
    add_reputation_adjustment,
    apply_vote,
    count_voters,
    list_due_lobbies_for_reputation,
    lobby_participant_ids,
    reputation_leaderboard,
    user_reputation_score,
)
from app.bot.reputation_roles import reputation_role_targets
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_due_lobbies_respect_delay(session: AsyncSession, event_bus: EventBus) -> None:
    session.add(Guild(discord_guild_id=90, name="R"))
    await upsert_user(session, 1, "Host")
    await session.commit()
    now = datetime.now(UTC)

    async with session.begin():
        host = await upsert_user(session, 1, "Host")
        recent = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="REP001",
            expires_in=timedelta(minutes=45),
            discord_guild_id=90,
        )
        recent.created_at = now - timedelta(minutes=49)
        old = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="REP002",
            expires_in=timedelta(minutes=45),
            discord_guild_id=90,
        )
        old.created_at = now - timedelta(minutes=50)

    enabled = now - timedelta(minutes=55)
    async with session.begin():
        due = await list_due_lobbies_for_reputation(
            session,
            discord_guild_id=90,
            delay_minutes=50,
            enabled_after=enabled,
            now=now,
        )
    assert len(due) == 1
    assert due[0].id == old.id

    async with session.begin():
        due_before = await list_due_lobbies_for_reputation(
            session,
            discord_guild_id=90,
            delay_minutes=50,
            enabled_after=now - timedelta(minutes=30),
            now=now,
        )
    assert due_before == []


@pytest.mark.asyncio
async def test_vote_cap_four(session: AsyncSession, event_bus: EventBus) -> None:
    session.add(Guild(discord_guild_id=93, name="Cap"))
    await upsert_user(session, 2, "Host")
    for voter in range(1, 6):
        await upsert_user(session, 1000 + voter, f"V{voter}")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 2, "Host")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="CAP001",
            expires_in=timedelta(minutes=45),
            discord_guild_id=93,
        )
        lobby_id = lobby.id

    for voter in range(1, 6):
        async with session.begin():
            result = await apply_vote(
                session, lobby_id=lobby_id, voter_id=1000 + voter, value=1
            )
        if voter <= 4:
            assert result.accepted
        else:
            assert not result.accepted
            assert result.reason == "cap_reached"

    async with session.begin():
        assert await count_voters(session, lobby_id) == 4


@pytest.mark.asyncio
async def test_reputation_score_applies_to_all_participants(
    session: AsyncSession, event_bus: EventBus
) -> None:
    session.add(Guild(discord_guild_id=91, name="A"))
    session.add(Guild(discord_guild_id=92, name="B"))
    await upsert_user(session, 10, "Host")
    await upsert_user(session, 11, "P1")
    await upsert_user(session, 12, "P2")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 10, "Host")
        p1 = await upsert_user(session, 11, "P1")
        lobby_a = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=3,
            party_code="SCOR01",
            expires_in=timedelta(minutes=45),
            discord_guild_id=91,
        )
        await join_lobby(session, event_bus, lobby_id=lobby_a.id, user=p1)
        session.add(
            LobbyReputationPost(
                lobby_id=lobby_a.id,
                channel_id=999,
                message_id=1,
            )
        )
        await upsert_user(session, 500, "VoterA")
        await apply_vote(session, lobby_id=lobby_a.id, voter_id=500, value=1)

        host_b = await upsert_user(session, 10, "Host")
        lobby_b = await create_lobby(
            session,
            event_bus,
            host=host_b,
            mode="Unrated",
            slots=2,
            party_code="SCOR02",
            expires_in=timedelta(minutes=45),
            discord_guild_id=92,
        )
        session.add(
            LobbyReputationPost(
                lobby_id=lobby_b.id,
                channel_id=999,
                message_id=2,
            )
        )
        await upsert_user(session, 501, "VoterB")
        await apply_vote(session, lobby_id=lobby_b.id, voter_id=501, value=-1)

    async with session.begin():
        participants = await lobby_participant_ids(session, lobby_a.id)
        assert participants == [10, 11]
        top_a = await reputation_leaderboard(session, discord_guild_id=91, limit=10)
        top_b = await reputation_leaderboard(session, discord_guild_id=92, limit=10)

    assert {e.user_id: e.score for e in top_a} == {10: 1, 11: 1}
    assert top_b[0].user_id == 10 and top_b[0].score == -1


def test_reputation_role_targets() -> None:
    class _Cfg:
        reputation_negative_role_id = 100
        reputation_negative_threshold = -15
        reputation_positive_role_id = 200
        reputation_positive_threshold = 25

    cfg = _Cfg()
    assert reputation_role_targets(cfg, -20) == (True, False)
    assert reputation_role_targets(cfg, 30) == (False, True)
    assert reputation_role_targets(cfg, 0) == (False, False)


@pytest.mark.asyncio
async def test_staff_adjustment_updates_score(session: AsyncSession) -> None:
    session.add(Guild(discord_guild_id=94, name="Adj"))
    await upsert_user(session, 20, "Player")
    await upsert_user(session, 99, "Staff")
    await session.commit()

    async with session.begin():
        total = await add_reputation_adjustment(
            session,
            discord_guild_id=94,
            user_id=20,
            delta=10,
            created_by_id=99,
        )
        assert total == 10
        total2 = await add_reputation_adjustment(
            session,
            discord_guild_id=94,
            user_id=20,
            delta=-3,
            created_by_id=99,
        )
        assert total2 == 7

    async with session.begin():
        assert (
            await user_reputation_score(session, discord_guild_id=94, user_id=20) == 7
        )
        board = await reputation_leaderboard(session, discord_guild_id=94, limit=5)
    assert board == [ReputationLeaderboardEntry(user_id=20, score=7)]
