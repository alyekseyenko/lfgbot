from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

_CACHE_TTL_SECONDS = 300.0
_CACHE: dict[int, tuple[float, list[dict[str, Any]]]] = {}
_LOCKS: dict[int, asyncio.Lock] = {}


async def get_discord_guilds(
    user_id: int,
    fetcher: Callable[[], Awaitable[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    now = time.time()
    cached = _CACHE.get(user_id)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    lock = _LOCKS.setdefault(user_id, asyncio.Lock())
    async with lock:
        cached = _CACHE.get(user_id)
        if cached is not None and time.time() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
        guilds = await fetcher()
        _CACHE[user_id] = (time.time(), guilds)
        return guilds


def store_discord_guilds(user_id: int, guilds: list[dict[str, Any]]) -> None:
    _CACHE[user_id] = (time.time(), guilds)


def invalidate_discord_guilds(user_id: int) -> None:
    _CACHE.pop(user_id, None)
