from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.ranking_embed import build_all_time_creators_embed
from app.core.events import EventBus
from app.db.models import Guild
from app.services.creator_levels import (
    CreatorLevelDef,
    all_time_top_creators,
    count_rooms_created,
    default_creator_levels,
    ensure_default_creator_levels,
    replace_creator_levels,
    resolve_creator_progress,
)
from app.services.gamification import WeeklyEntry, profile_stats
from app.services.lobbies import create_lobby
from app.services.users import upsert_user


def test_resolve_creator_progress_thresholds() -> None:
    levels = default_creator_levels()
    zero = resolve_creator_progress(0, levels)
    assert zero.current is None
    assert zero.level_name == "—"
    assert zero.next_level is not None
    assert zero.next_level.name == "Recruta"

    one = resolve_creator_progress(1, levels)
    assert one.level_name == "Recruta"
    assert one.next_level is not None
    assert one.next_level.name == "Anfitrião"

    hundred = resolve_creator_progress(100, levels)
    assert hundred.level_name == "Lenda"
    assert hundred.next_level is None
    assert "máximo" in hundred.next_level_hint


def test_all_time_ranking_embed_empty() -> None:
    embed = build_all_time_creators_embed([], {})
    assert "histórico" in (embed.description or "").lower() or "completo" in (
        embed.description or ""
    ).lower()
    field = embed.fields[0]
    assert "ninguém" in (field.value or "").lower()


def test_all_time_ranking_embed_order() -> None:
    embed = build_all_time_creators_embed(
        [
            WeeklyEntry(user_id=1, count=12),
            WeeklyEntry(user_id=2, count=3),
        ],
        {1: "Ana", 2: "Beto"},
    )
    value = embed.fields[0].value or ""
    assert "Ana" in value
    assert "12" in value
    assert value.index("Ana") < value.index("Beto")


@pytest.mark.asyncio
async def test_count_and_leaderboard_by_guild(
    session: AsyncSession, event_bus: EventBus
) -> None:
    session.add(Guild(discord_guild_id=77, name="Test"))
    await upsert_user(session, 11, "HostA")
    await upsert_user(session, 12, "HostB")
    await session.commit()

    async with session.begin():
        host_a = await upsert_user(session, 11, "HostA")
        host_b = await upsert_user(session, 12, "HostB")
        await create_lobby(
            session,
            event_bus,
            host=host_a,
            mode="Unrated",
            slots=2,
            party_code="AAA111",
            expires_in=timedelta(minutes=30),
            discord_guild_id=77,
        )
        await create_lobby(
            session,
            event_bus,
            host=host_a,
            mode="Unrated",
            slots=2,
            party_code="AAA222",
            expires_in=timedelta(minutes=30),
            discord_guild_id=77,
        )
        await create_lobby(
            session,
            event_bus,
            host=host_b,
            mode="Unrated",
            slots=2,
            party_code="BBB111",
            expires_in=timedelta(minutes=30),
            discord_guild_id=77,
        )
        await create_lobby(
            session,
            event_bus,
            host=host_a,
            mode="Unrated",
            slots=2,
            party_code="OTH3R1",
            expires_in=timedelta(minutes=30),
            discord_guild_id=88,
        )

    async with session.begin():
        assert await count_rooms_created(session, 11, discord_guild_id=77) == 2
        top = await all_time_top_creators(session, discord_guild_id=77, limit=10)
        page2 = await all_time_top_creators(session, discord_guild_id=77, limit=1, offset=1)
    assert [(e.user_id, e.count) for e in top] == [(11, 2), (12, 1)]
    assert [(e.user_id, e.count) for e in page2] == [(12, 1)]


@pytest.mark.asyncio
async def test_default_levels_seed_and_replace(session: AsyncSession) -> None:
    session.add(Guild(discord_guild_id=55, name="Seed"))
    await session.commit()

    async with session.begin():
        seeded = await ensure_default_creator_levels(session, 55)
    assert [item.name for item in seeded][:2] == ["Recruta", "Anfitrião"]

    async with session.begin():
        again = await ensure_default_creator_levels(session, 55)
    assert len(again) == len(seeded)

    async with session.begin():
        saved = await replace_creator_levels(
            session,
            55,
            [
                CreatorLevelDef(1, "Iniciante", 1, None),
                CreatorLevelDef(2, "Pro", 10, 123),
            ],
        )
    assert saved[1].discord_role_id == 123
    assert saved[0].name == "Iniciante"


@pytest.mark.asyncio
async def test_profile_stats_uses_rooms_created(
    session: AsyncSession, event_bus: EventBus
) -> None:
    session.add(Guild(discord_guild_id=66, name="P"))
    await upsert_user(session, 21, "Host")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 21, "Host")
        for i in range(5):
            await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=2,
                party_code=f"C{i:03d}XX",
                expires_in=timedelta(minutes=30),
                discord_guild_id=66,
            )

    stats = await profile_stats(session, 21, discord_guild_id=66)
    assert stats.rooms_created == 5
    assert stats.level == "Anfitrião"
    assert stats.next_min_rooms == 15
    assert "Organizador" in stats.next_level_hint
