from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lobby, LobbyState
from app.services.errors import PartyCodeInUseError


def normalize_party_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    code = raw.strip().upper()
    return code or None


async def assert_party_code_available_for_guild(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    party_code: str | None,
    now: datetime,
    exclude_lobby_id: UUID | None = None,
) -> None:
    normalized = normalize_party_code(party_code)
    if normalized is None:
        return

    query = (
        select(Lobby.id)
        .where(
            Lobby.discord_guild_id == discord_guild_id,
            Lobby.party_code == normalized,
            Lobby.state.in_((LobbyState.open, LobbyState.full)),
            Lobby.expires_at > now,
        )
        .with_for_update()
    )
    if exclude_lobby_id is not None:
        query = query.where(Lobby.id != exclude_lobby_id)

    result = await session.execute(query.limit(1))
    if result.scalar_one_or_none() is not None:
        raise PartyCodeInUseError(
            "Já existe um pedido ativo com este código de party neste servidor. "
            "Espera que o outro feche ou usa outro código."
        )
