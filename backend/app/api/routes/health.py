from __future__ import annotations

import time
from typing import Any

import discord
from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict[str, Any]:
    state = request.app.state.api_state
    session_factory: async_sessionmaker[AsyncSession] = state.session_factory
    bot: discord.Client | None = state.bot

    checks: dict[str, Any] = {}
    ok = True

    db_started = time.perf_counter()
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {
            "ok": True,
            "latency_ms": round((time.perf_counter() - db_started) * 1000, 2),
        }
    except Exception as exc:
        ok = False
        checks["database"] = {"ok": False, "error": type(exc).__name__}

    if bot is None:
        ok = False
        checks["discord_gateway"] = {"ok": False, "error": "bot_not_configured"}
    elif not bot.is_ready():
        ok = False
        checks["discord_gateway"] = {"ok": False, "error": "not_ready"}
    else:
        latency_ms = round(bot.latency * 1000, 2)
        checks["discord_gateway"] = {"ok": True, "latency_ms": latency_ms}

    body = {"status": "ok" if ok else "degraded", "checks": checks}
    if not ok:
        response.status_code = 503
    return body
