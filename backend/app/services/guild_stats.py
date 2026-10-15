from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.db.models import Lobby, LobbyCompletion, LobbyMember, LobbyState
from app.services.lobby_source import (
    LOBBY_SOURCE_CHAT,
    LOBBY_SOURCE_PANEL,
    LOBBY_SOURCE_SLASH,
    LOBBY_SOURCE_UNKNOWN,
)


def _guild_lobby_scope(discord_guild_id: int, channel_ids: list[int]) -> ColumnElement[bool]:
    if channel_ids:
        return or_(
            Lobby.discord_guild_id == discord_guild_id,
            and_(
                Lobby.discord_guild_id.is_(None),
                Lobby.channel_id.in_(channel_ids),
            ),
        )
    return Lobby.discord_guild_id == discord_guild_id


async def guild_lobby_stats(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    channel_ids: list[int],
    days: int = 30,
) -> dict[str, int | float | dict[str, int]]:
    scope = _guild_lobby_scope(discord_guild_id, channel_ids)
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    since_7d = now - timedelta(days=7)

    if not channel_ids and discord_guild_id == 0:
        empty_sources = {
            LOBBY_SOURCE_SLASH: 0,
            LOBBY_SOURCE_PANEL: 0,
            LOBBY_SOURCE_CHAT: 0,
            LOBBY_SOURCE_UNKNOWN: 0,
        }
        return {
            "active_lobbies": 0,
            "lobbies_created_period": 0,
            "joins_period": 0,
            "active_users_7d": 0,
            "groups_filled_period": 0,
            "groups_completed_period": 0,
            "avg_minutes_to_fill": 0.0,
            "avg_minutes_to_end": 0.0,
            "created_by_source": empty_sources,
        }

    active_result = await session.execute(
        select(func.count())
        .select_from(Lobby)
        .where(
            scope,
            Lobby.state.in_((LobbyState.open, LobbyState.full)),
            Lobby.expires_at > now,
        )
    )
    created_result = await session.execute(
        select(func.count()).select_from(Lobby).where(scope, Lobby.created_at >= since)
    )
    joins_result = await session.execute(
        select(func.count())
        .select_from(LobbyMember)
        .join(Lobby, Lobby.id == LobbyMember.lobby_id)
        .where(scope, LobbyMember.joined_at >= since)
    )

    filled_result = await session.execute(
        select(func.count())
        .select_from(Lobby)
        .where(scope, Lobby.filled_at.is_not(None), Lobby.filled_at >= since)
    )

    completed_result = await session.execute(
        select(func.count(func.distinct(LobbyCompletion.lobby_id)))
        .select_from(LobbyCompletion)
        .join(Lobby, Lobby.id == LobbyCompletion.lobby_id)
        .where(scope, LobbyCompletion.awarded_at >= since)
    )

    avg_fill_result = await session.execute(
        select(func.avg(func.extract("epoch", Lobby.filled_at - Lobby.created_at) / 60.0))
        .select_from(Lobby)
        .where(scope, Lobby.filled_at.is_not(None), Lobby.created_at >= since)
    )
    avg_end_result = await session.execute(
        select(func.avg(func.extract("epoch", Lobby.ended_at - Lobby.created_at) / 60.0))
        .select_from(Lobby)
        .where(scope, Lobby.ended_at.is_not(None), Lobby.created_at >= since)
    )

    hosts_7d = await session.execute(
        select(Lobby.host_id).where(scope, Lobby.created_at >= since_7d).distinct()
    )
    members_7d = await session.execute(
        select(LobbyMember.user_id)
        .select_from(LobbyMember)
        .join(Lobby, Lobby.id == LobbyMember.lobby_id)
        .where(scope, LobbyMember.joined_at >= since_7d)
        .distinct()
    )
    active_users_7d = len(
        {int(row[0]) for row in hosts_7d.all()} | {int(row[0]) for row in members_7d.all()}
    )

    source_rows = await session.execute(
        select(Lobby.create_source, func.count())
        .where(scope, Lobby.created_at >= since)
        .group_by(Lobby.create_source)
    )
    created_by_source = {
        LOBBY_SOURCE_SLASH: 0,
        LOBBY_SOURCE_PANEL: 0,
        LOBBY_SOURCE_CHAT: 0,
        LOBBY_SOURCE_UNKNOWN: 0,
    }
    for source, count in source_rows.all():
        key = source if source in created_by_source else LOBBY_SOURCE_UNKNOWN
        created_by_source[key] = int(count)

    avg_fill = avg_fill_result.scalar_one()
    avg_end = avg_end_result.scalar_one()

    return {
        "active_lobbies": int(active_result.scalar_one()),
        "lobbies_created_period": int(created_result.scalar_one()),
        "joins_period": int(joins_result.scalar_one()),
        "active_users_7d": active_users_7d,
        "groups_filled_period": int(filled_result.scalar_one()),
        "groups_completed_period": int(completed_result.scalar_one()),
        "avg_minutes_to_fill": round(float(avg_fill or 0.0), 1),
        "avg_minutes_to_end": round(float(avg_end or 0.0), 1),
        "created_by_source": created_by_source,
    }
