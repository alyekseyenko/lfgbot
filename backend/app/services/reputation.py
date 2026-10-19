from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import discord
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GuildReputationAdjustment,
    Lobby,
    LobbyMember,
    LobbyReputationPost,
    LobbyReputationVote,
)

REACTION_THUMBS_UP = "\N{THUMBS UP SIGN}"
REACTION_THUMBS_DOWN = "\N{THUMBS DOWN SIGN}"
MAX_VOTERS_PER_LOBBY = 4
DEFAULT_REPUTATION_DELAY_MINUTES = 50
MIN_REPUTATION_DELAY_MINUTES = 10
MAX_REPUTATION_DELAY_MINUTES = 180
DEFAULT_REPUTATION_NEGATIVE_THRESHOLD = -15
DEFAULT_REPUTATION_POSITIVE_THRESHOLD = 25
MIN_REPUTATION_ADJUST_DELTA = -500
MAX_REPUTATION_ADJUST_DELTA = 500


@dataclass(frozen=True, slots=True)
class ReputationLeaderboardEntry:
    user_id: int
    score: int


@dataclass(frozen=True, slots=True)
class VoteApplyResult:
    accepted: bool
    reason: str | None = None
    value: int | None = None
    voter_id: int | None = None


def clamp_reputation_negative_threshold(value: int) -> int:
    return max(-10_000, min(-1, int(value)))


def clamp_reputation_positive_threshold(value: int) -> int:
    return max(1, min(10_000, int(value)))


def clamp_reputation_adjust_delta(delta: int) -> int:
    return max(MIN_REPUTATION_ADJUST_DELTA, min(MAX_REPUTATION_ADJUST_DELTA, int(delta)))


def clamp_reputation_delay_minutes(minutes: int) -> int:
    return max(
        MIN_REPUTATION_DELAY_MINUTES,
        min(MAX_REPUTATION_DELAY_MINUTES, int(minutes)),
    )


def partial_emoji_value(emoji: discord.PartialEmoji) -> int | None:
    if emoji.id is not None:
        return None
    name = emoji.name or ""
    if name in (REACTION_THUMBS_UP, "👍", "thumbsup", "+1"):
        return 1
    if name in (REACTION_THUMBS_DOWN, "👎", "thumbsdown", "-1"):
        return -1
    return None


async def lobby_participant_ids(session: AsyncSession, lobby_id: UUID) -> list[int]:
    lobby = await session.get(Lobby, lobby_id)
    if lobby is None:
        return []
    ids: set[int] = {int(lobby.host_id)}
    result = await session.execute(
        select(LobbyMember.user_id).where(LobbyMember.lobby_id == lobby_id)
    )
    for (user_id,) in result.all():
        ids.add(int(user_id))
    return sorted(ids)


async def list_due_lobbies_for_reputation(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    delay_minutes: int,
    enabled_after: datetime | None = None,
    now: datetime | None = None,
    limit: int = 25,
) -> list[Lobby]:
    now = now or datetime.now(UTC)
    delay = timedelta(minutes=clamp_reputation_delay_minutes(delay_minutes))
    cutoff = now - delay
    has_post = exists().where(LobbyReputationPost.lobby_id == Lobby.id)
    stmt = select(Lobby).where(
        Lobby.discord_guild_id == discord_guild_id,
        Lobby.created_at <= cutoff,
        ~has_post,
    )
    if enabled_after is not None:
        stmt = stmt.where(Lobby.created_at >= enabled_after)
    result = await session.execute(
        stmt.order_by(Lobby.created_at.asc()).limit(limit)
    )
    return list(result.scalars())


async def save_reputation_post(
    session: AsyncSession,
    *,
    lobby_id: UUID,
    channel_id: int,
    message_id: int,
) -> None:
    session.add(
        LobbyReputationPost(
            lobby_id=lobby_id,
            channel_id=channel_id,
            message_id=message_id,
        )
    )
    await session.flush()


async def get_reputation_post_by_message(
    session: AsyncSession, channel_id: int, message_id: int
) -> LobbyReputationPost | None:
    result = await session.execute(
        select(LobbyReputationPost).where(
            LobbyReputationPost.channel_id == channel_id,
            LobbyReputationPost.message_id == message_id,
        )
    )
    return result.scalar_one_or_none()


async def count_voters(session: AsyncSession, lobby_id: UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(LobbyReputationVote)
        .where(LobbyReputationVote.lobby_id == lobby_id)
    )
    return int(result.scalar_one())


async def get_vote(
    session: AsyncSession, lobby_id: UUID, voter_id: int
) -> LobbyReputationVote | None:
    return await session.get(LobbyReputationVote, (lobby_id, voter_id))


async def apply_vote(
    session: AsyncSession,
    *,
    lobby_id: UUID,
    voter_id: int,
    value: int,
) -> VoteApplyResult:
    if value not in (-1, 1):
        return VoteApplyResult(accepted=False, reason="invalid_value")
    existing = await get_vote(session, lobby_id, voter_id)
    if existing is None:
        count = await count_voters(session, lobby_id)
        if count >= MAX_VOTERS_PER_LOBBY:
            return VoteApplyResult(accepted=False, reason="cap_reached")
        session.add(
            LobbyReputationVote(lobby_id=lobby_id, voter_id=voter_id, value=value)
        )
    else:
        existing.value = value
    await session.flush()
    return VoteApplyResult(accepted=True, value=value, voter_id=voter_id)


async def clear_vote(session: AsyncSession, *, lobby_id: UUID, voter_id: int) -> bool:
    result = await session.execute(
        delete(LobbyReputationVote).where(
            LobbyReputationVote.lobby_id == lobby_id,
            LobbyReputationVote.voter_id == voter_id,
        )
    )
    await session.flush()
    return bool(result.rowcount)


async def _vote_reputation_scores(
    session: AsyncSession, discord_guild_id: int
) -> dict[int, int]:
    """Net score from votes: each vote on a lobby adds vote.value to every participant."""
    lobbies = select(Lobby.id).where(Lobby.discord_guild_id == discord_guild_id).scalar_subquery()
    votes = (
        select(
            LobbyReputationVote.lobby_id,
            LobbyReputationVote.value,
        ).where(LobbyReputationVote.lobby_id.in_(lobbies))
    )
    vote_rows = await session.execute(votes)
    vote_list = list(vote_rows.all())
    if not vote_list:
        return {}

    lobby_ids = {row[0] for row in vote_list}
    participant_map: dict[UUID, list[int]] = {}
    for lobby_id in lobby_ids:
        participant_map[lobby_id] = await lobby_participant_ids(session, lobby_id)

    scores: dict[int, int] = {}
    for lobby_id, vote_value in vote_list:
        for user_id in participant_map.get(lobby_id, []):
            scores[user_id] = scores.get(user_id, 0) + int(vote_value)
    return scores


async def _adjustment_reputation_scores(
    session: AsyncSession, discord_guild_id: int
) -> dict[int, int]:
    result = await session.execute(
        select(GuildReputationAdjustment.user_id, func.coalesce(func.sum(GuildReputationAdjustment.delta), 0))
        .where(GuildReputationAdjustment.discord_guild_id == discord_guild_id)
        .group_by(GuildReputationAdjustment.user_id)
    )
    return {int(user_id): int(total) for user_id, total in result.all()}


async def reputation_scores(
    session: AsyncSession, *, discord_guild_id: int
) -> dict[int, int]:
    scores = await _vote_reputation_scores(session, discord_guild_id)
    for user_id, delta in (await _adjustment_reputation_scores(session, discord_guild_id)).items():
        scores[user_id] = scores.get(user_id, 0) + delta
    return scores


async def user_reputation_score(
    session: AsyncSession, *, discord_guild_id: int, user_id: int
) -> int:
    return (await reputation_scores(session, discord_guild_id=discord_guild_id)).get(
        int(user_id), 0
    )


async def add_reputation_adjustment(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    user_id: int,
    delta: int,
    created_by_id: int,
) -> int:
    """Record staff adjustment; returns new total score for the user."""
    clamped = clamp_reputation_adjust_delta(delta)
    if clamped == 0:
        return await user_reputation_score(
            session, discord_guild_id=discord_guild_id, user_id=user_id
        )
    session.add(
        GuildReputationAdjustment(
            discord_guild_id=discord_guild_id,
            user_id=user_id,
            delta=clamped,
            created_by_id=created_by_id,
        )
    )
    await session.flush()
    return await user_reputation_score(
        session, discord_guild_id=discord_guild_id, user_id=user_id
    )


async def reputation_leaderboard(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[ReputationLeaderboardEntry]:
    scores = await reputation_scores(session, discord_guild_id=discord_guild_id)
    if not scores:
        return []

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    slice_start = max(0, offset)
    slice_end = slice_start + limit
    return [
        ReputationLeaderboardEntry(user_id=uid, score=score)
        for uid, score in ranked[slice_start:slice_end]
    ]


async def delete_adjustments_for_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        delete(GuildReputationAdjustment).where(GuildReputationAdjustment.user_id == user_id)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def delete_votes_by_voter(session: AsyncSession, voter_id: int) -> int:
    result = await session.execute(
        delete(LobbyReputationVote).where(LobbyReputationVote.voter_id == voter_id)
    )
    await session.flush()
    return int(result.rowcount or 0)
