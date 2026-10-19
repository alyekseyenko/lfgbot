from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import Guild
from app.services.creator_levels import (
    anchor_week_start_for_date,
    completed_anchor_week_to_post,
    creator_role_ids_for_levels,
    default_creator_levels,
    did_creator_level_up,
    weekly_top_creators_in_anchor_week,
)
from app.services.gamification import PORTUGAL
from app.services.lobbies import create_lobby
from app.services.users import upsert_user

LISBON = ZoneInfo("Europe/Lisbon")


def test_anchor_week_start_from_custom_anchor() -> None:
    anchor = date(2026, 1, 10)
    assert anchor_week_start_for_date(anchor, date(2026, 1, 9)) is None
    assert anchor_week_start_for_date(anchor, date(2026, 1, 10)) == date(2026, 1, 10)
    assert anchor_week_start_for_date(anchor, date(2026, 1, 16)) == date(2026, 1, 10)
    assert anchor_week_start_for_date(anchor, date(2026, 1, 17)) == date(2026, 1, 17)


def test_completed_anchor_week_to_post_at_week_end_21h() -> None:
    anchor = date(2026, 1, 10)
    week_start = date(2026, 1, 10)
    week_end = week_start + timedelta(days=6)
    ok = datetime(week_end.year, week_end.month, week_end.day, 21, 0, tzinfo=LISBON)
    assert completed_anchor_week_to_post(ok, anchor) == week_start
    too_early = datetime(week_end.year, week_end.month, week_end.day, 20, 59, tzinfo=LISBON)
    assert completed_anchor_week_to_post(too_early, anchor) is None
    wrong_day = datetime(2026, 1, 15, 21, 0, tzinfo=LISBON)
    assert completed_anchor_week_to_post(wrong_day, anchor) is None


def test_did_creator_level_up_anfitriao_at_five_not_at_six() -> None:
    levels = default_creator_levels()
    up, after, _ = did_creator_level_up(4, 5, levels)
    assert up is True
    assert after.level_name == "Anfitrião"
    no_up, after_six, _ = did_creator_level_up(5, 6, levels)
    assert no_up is False
    assert after_six.level_name == "Anfitrião"


def test_creator_role_ids_for_levels() -> None:
    from app.services.creator_levels import CreatorLevelDef

    levels = [
        CreatorLevelDef(1, "A", 1, 50),
        CreatorLevelDef(2, "B", 5, 100),
        CreatorLevelDef(3, "C", 15, 200),
    ]
    assert creator_role_ids_for_levels(levels) == (50, 100, 200)


@pytest.mark.asyncio
async def test_weekly_top_creators_respects_anchor_window_and_guild(
    session: AsyncSession, event_bus: EventBus
) -> None:
    session.add(Guild(discord_guild_id=70, name="A"))
    session.add(Guild(discord_guild_id=71, name="B"))
    await upsert_user(session, 30, "Host")
    await session.commit()

    anchor = date(2026, 3, 1)
    week_start = anchor
    start_local = datetime(week_start.year, week_start.month, week_start.day, tzinfo=PORTUGAL)
    in_week = start_local + timedelta(days=2)

    from datetime import UTC

    async with session.begin():
        host = await upsert_user(session, 30, "Host")
        for i, (gid, code) in enumerate([(70, "W1A111"), (70, "W1A222"), (71, "W1B111")]):
            lobby = await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=2,
                party_code=code,
                expires_in=timedelta(minutes=30),
                discord_guild_id=gid,
            )
            lobby.created_at = in_week.astimezone(UTC) + timedelta(minutes=i)

    async with session.begin():
        top70 = await weekly_top_creators_in_anchor_week(
            session, discord_guild_id=70, week_start=week_start, limit=10
        )
        top71 = await weekly_top_creators_in_anchor_week(
            session, discord_guild_id=71, week_start=week_start, limit=10
        )
    assert [(e.user_id, e.count) for e in top70] == [(30, 2)]
    assert [(e.user_id, e.count) for e in top71] == [(30, 1)]
