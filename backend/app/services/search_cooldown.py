from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.errors import SearchBlockedError

PORTUGAL = ZoneInfo("Europe/Lisbon")

LEAVE_REASON_LEFT = "left"
LEAVE_REASON_KICKED = "kicked"
LEAVE_REASON_CLOSED = "closed"
LEAVE_REASON_EXPIRED = "expired"


def cooldown_duration_for_daily_count(count: int) -> timedelta:
    if count <= 3:
        return timedelta(minutes=5)
    if count == 4:
        return timedelta(minutes=15)
    return timedelta(hours=12)


def format_search_blocked_until(until: datetime) -> str:
    local = until.astimezone(PORTUGAL)
    return f"Podes procurar outra party às {local.strftime('%H:%M')} (hora de Lisboa)."


def assert_can_search(user: User, now: datetime) -> None:
    if user.search_blocked_until is not None and user.search_blocked_until > now:
        raise SearchBlockedError(format_search_blocked_until(user.search_blocked_until))


async def apply_private_voluntary_leave_penalty(
    session: AsyncSession, user: User, now: datetime
) -> datetime:
    today = now.astimezone(PORTUGAL).date()
    if user.private_leave_day != today:
        user.private_leave_day = today
        user.private_leave_count = 0

    user.private_leave_count += 1
    duration = cooldown_duration_for_daily_count(user.private_leave_count)
    blocked_until = now + duration
    if user.search_blocked_until is None or blocked_until > user.search_blocked_until:
        user.search_blocked_until = blocked_until

    await session.flush()
    return blocked_until
