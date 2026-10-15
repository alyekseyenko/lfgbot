"""Observabilidade leve de interações Discord (ack + contexto de log)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import discord

from app.core.log_context import log_context
from app.core.metrics import interaction_latency_seconds


@asynccontextmanager
async def track_interaction(
    interaction: discord.Interaction,
    *,
    lobby_id: str | None = None,
) -> AsyncIterator[float]:
    user_id = interaction.user.id if interaction.user else None
    started = time.perf_counter()
    with log_context(
        guild_id=interaction.guild_id,
        lobby_id=lobby_id,
        interaction_id=str(interaction.id),
        user_id=user_id,
    ):
        yield started
    if interaction.response.is_done():
        interaction_latency_seconds.observe(time.perf_counter() - started)
