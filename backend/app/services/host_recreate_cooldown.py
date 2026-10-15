from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import User

PORTUGAL = ZoneInfo("Europe/Lisbon")

DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS = 300
DEFAULT_IMMUNE_HOST_RECREATE_COOLDOWN_SECONDS = 10


def clamp_host_recreate_seconds(seconds: int) -> int:
    return max(0, min(int(seconds), 24 * 3600))


def format_host_recreate_blocked_until(until: datetime) -> str:
    local = until.astimezone(PORTUGAL)
    return f"Podes criar outro pedido às {local.strftime('%H:%M')} (hora de Lisboa)."


def assert_can_host_create(user: User, now: datetime) -> None:
    from app.services.errors import HostRecreateBlockedError

    if user.host_create_blocked_until is not None and user.host_create_blocked_until > now:
        raise HostRecreateBlockedError(
            format_host_recreate_blocked_until(user.host_create_blocked_until)
        )


def apply_host_recreate_cooldown(user: User, now: datetime, duration: timedelta) -> datetime | None:
    """Define o bloqueio após fechar um pedido (substitui o anterior).

    O tempo depende das roles isentas do host no momento do fecho (ex. 10 s vs 300 s).
    """
    if duration <= timedelta(0):
        user.host_create_blocked_until = None
        return None
    blocked_until = now + duration
    user.host_create_blocked_until = blocked_until
    return blocked_until
