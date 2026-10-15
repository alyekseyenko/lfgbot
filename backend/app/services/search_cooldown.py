from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.errors import SearchBlockedError

PORTUGAL = ZoneInfo("Europe/Lisbon")

LEAVE_REASON_LEFT = "left"
LEAVE_REASON_KICKED = "kicked"
LEAVE_REASON_CLOSED = "closed"
LEAVE_REASON_EXPIRED = "expired"

DEFAULT_EARLY_MAX_COUNT = 3
DEFAULT_EARLY_MINUTES = 5
DEFAULT_MID_MINUTES = 15
DEFAULT_SEVERE_HOURS = 12


@dataclass(frozen=True, slots=True)
class SearchCooldownPolicy:
    enabled: bool = True
    early_minutes: int = DEFAULT_EARLY_MINUTES
    early_max_daily_count: int = DEFAULT_EARLY_MAX_COUNT
    mid_minutes: int = DEFAULT_MID_MINUTES
    severe_hours: int = DEFAULT_SEVERE_HOURS


def _clamp_policy(policy: SearchCooldownPolicy) -> SearchCooldownPolicy:
    return SearchCooldownPolicy(
        enabled=policy.enabled,
        early_minutes=max(1, min(policy.early_minutes, 24 * 60)),
        early_max_daily_count=max(1, min(policy.early_max_daily_count, 20)),
        mid_minutes=max(1, min(policy.mid_minutes, 24 * 60)),
        severe_hours=max(1, min(policy.severe_hours, 24 * 7)),
    )


def cooldown_duration_for_daily_count(
    count: int,
    policy: SearchCooldownPolicy | None = None,
) -> timedelta:
    resolved = _clamp_policy(policy or SearchCooldownPolicy())
    if not resolved.enabled:
        return timedelta(0)
    if count <= resolved.early_max_daily_count:
        return timedelta(minutes=resolved.early_minutes)
    if count == resolved.early_max_daily_count + 1:
        return timedelta(minutes=resolved.mid_minutes)
    return timedelta(hours=resolved.severe_hours)


def format_search_blocked_until(until: datetime) -> str:
    local = until.astimezone(PORTUGAL)
    return f"Podes procurar outra party às {local.strftime('%H:%M')} (hora de Lisboa)."


def assert_can_search(user: User, now: datetime) -> None:
    if user.search_blocked_until is not None and user.search_blocked_until > now:
        raise SearchBlockedError(format_search_blocked_until(user.search_blocked_until))


async def apply_private_voluntary_leave_penalty(
    session: AsyncSession,
    user: User,
    now: datetime,
    *,
    policy: SearchCooldownPolicy | None = None,
) -> datetime | None:
    resolved = _clamp_policy(policy or SearchCooldownPolicy())
    if not resolved.enabled:
        return None

    today = now.astimezone(PORTUGAL).date()
    if user.private_leave_day != today:
        user.private_leave_day = today
        user.private_leave_count = 0

    user.private_leave_count += 1
    duration = cooldown_duration_for_daily_count(user.private_leave_count, resolved)
    if duration <= timedelta(0):
        return None

    blocked_until = now + duration
    if user.search_blocked_until is None or blocked_until > user.search_blocked_until:
        user.search_blocked_until = blocked_until

    await session.flush()
    return blocked_until
