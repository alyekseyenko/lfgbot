from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LobbyCompletion, LobbyMember, User
from app.services.reputation import delete_adjustments_for_user, delete_votes_by_voter

DELETED_USER_DISPLAY_NAME = "Utilizador removido (RGPD)"


@dataclass(frozen=True, slots=True)
class UserDataDeletionResult:
    discord_id: int
    memberships_removed: int
    completions_removed: int
    reputation_votes_removed: int
    reputation_adjustments_removed: int
    user_anonymized: bool


async def delete_user_personal_data(
    session: AsyncSession,
    discord_id: int,
) -> UserDataDeletionResult:
    """Remove PII and participation rows; keep host lobbies with anonymized host name."""
    user = await session.get(User, discord_id)
    if user is None:
        return UserDataDeletionResult(
            discord_id=discord_id,
            memberships_removed=0,
            completions_removed=0,
            reputation_votes_removed=0,
            reputation_adjustments_removed=0,
            user_anonymized=False,
        )

    members_result = cast(
        CursorResult[Any],
        await session.execute(delete(LobbyMember).where(LobbyMember.user_id == discord_id)),
    )
    completions_result = cast(
        CursorResult[Any],
        await session.execute(delete(LobbyCompletion).where(LobbyCompletion.user_id == discord_id)),
    )
    reputation_votes_removed = await delete_votes_by_voter(session, discord_id)
    reputation_adjustments_removed = await delete_adjustments_for_user(session, discord_id)

    user.name = DELETED_USER_DISPLAY_NAME
    user.rank = None
    user.search_blocked_until = None
    user.host_create_blocked_until = None
    user.private_leave_day = None
    user.private_leave_count = 0
    user.riot_game_name = None
    user.riot_tag = None
    user.player_card_uuid = None

    await session.flush()
    return UserDataDeletionResult(
        discord_id=discord_id,
        memberships_removed=int(members_result.rowcount or 0),
        completions_removed=int(completions_result.rowcount or 0),
        reputation_votes_removed=reputation_votes_removed,
        reputation_adjustments_removed=reputation_adjustments_removed,
        user_anonymized=True,
    )


async def user_exists(session: AsyncSession, discord_id: int) -> bool:
    result = await session.execute(
        select(User.discord_id).where(User.discord_id == discord_id).limit(1)
    )
    return result.scalar_one_or_none() is not None
