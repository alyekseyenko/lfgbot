"""Contexto de logging (guild, lobby, interação) e hash de utilizador (RGPD)."""

from __future__ import annotations

import contextvars
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

guild_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar("guild_id", default=None)
lobby_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("lobby_id", default=None)
interaction_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "interaction_id", default=None
)
user_hash_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_hash", default=None
)


def hash_discord_user_id(user_id: int) -> str:
    digest = hashlib.sha256(str(user_id).encode()).hexdigest()
    return digest[:12]


@contextmanager
def log_context(
    *,
    guild_id: int | None = None,
    lobby_id: UUID | str | None = None,
    interaction_id: str | None = None,
    user_id: int | None = None,
) -> Iterator[None]:
    tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = []
    if guild_id is not None:
        tokens.append((guild_id_ctx, guild_id_ctx.set(guild_id)))
    if lobby_id is not None:
        tokens.append((lobby_id_ctx, lobby_id_ctx.set(str(lobby_id))))
    if interaction_id is not None:
        tokens.append((interaction_id_ctx, interaction_id_ctx.set(interaction_id)))
    if user_id is not None:
        tokens.append((user_hash_ctx, user_hash_ctx.set(hash_discord_user_id(user_id))))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def current_log_extras() -> dict[str, str | int]:
    out: dict[str, str | int] = {}
    guild_id = guild_id_ctx.get()
    if guild_id is not None:
        out["guild_id"] = guild_id
    lobby_id = lobby_id_ctx.get()
    if lobby_id is not None:
        out["lobby_id"] = lobby_id
    interaction_id = interaction_id_ctx.get()
    if interaction_id is not None:
        out["interaction_id"] = interaction_id
    user_hash = user_hash_ctx.get()
    if user_hash is not None:
        out["user_hash"] = user_hash
    return out
