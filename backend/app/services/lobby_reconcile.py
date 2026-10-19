"""Reproject active lobby state from the database onto Discord embeds."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.lobbies import list_active_lobbies


async def reconcile_active_lobby_embeds(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    refresh: Callable[[UUID], Awaitable[None]],
) -> int:
    """Refresh Discord embeds for all open/full lobbies. Returns count refreshed."""
    async with session_factory() as session:
        active = await list_active_lobbies(session)
    for lobby in active:
        await refresh(lobby.id)
    return len(active)
