from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lobby, LobbyState
from app.services.errors import PartyCodeInUseError, PartyCodeInvalidError

DEFAULT_PARTY_CODE_MAX_LENGTH = 6
# Compat: usado em scripts e imports antigos.
PARTY_CODE_LENGTH = DEFAULT_PARTY_CODE_MAX_LENGTH

MIN_PARTY_CODE_MAX_LENGTH = 4
MAX_PARTY_CODE_MAX_LENGTH = 12


def clamp_party_code_max_length(value: int) -> int:
    return max(MIN_PARTY_CODE_MAX_LENGTH, min(MAX_PARTY_CODE_MAX_LENGTH, int(value)))


def party_code_pattern(max_length: int) -> re.Pattern[str]:
    length = clamp_party_code_max_length(max_length)
    return re.compile(rf"^[A-Z0-9]{{{length}}}$")


def party_code_invalid_message(max_length: int) -> str:
    n = clamp_party_code_max_length(max_length)
    return (
        f"O código da party tem de ter **{n} caracteres** "
        "(letras e números, como no jogo). Não incluas espaços nem texto extra."
    )


def normalize_party_code(
    raw: str | None,
    *,
    max_length: int = DEFAULT_PARTY_CODE_MAX_LENGTH,
) -> str | None:
    if raw is None:
        return None
    code = raw.strip().upper()
    if not code:
        return None
    limit = clamp_party_code_max_length(max_length)
    pattern = party_code_pattern(limit)
    if len(code) != limit or not pattern.match(code):
        raise PartyCodeInvalidError(party_code_invalid_message(limit))
    if not any(ch.isdigit() for ch in code):
        raise PartyCodeInvalidError(party_code_invalid_message(limit))
    return code


async def assert_party_code_available_for_guild(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    party_code: str | None,
    now: datetime,
    exclude_lobby_id: UUID | None = None,
    party_code_max_length: int = DEFAULT_PARTY_CODE_MAX_LENGTH,
) -> None:
    normalized = normalize_party_code(
        party_code, max_length=party_code_max_length
    )
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
            "Já há um pedido **ativo** com este código neste servidor. "
            "Fecha aquele post (**Fechar**), espera expirar, ou usa **outro código**."
        )
