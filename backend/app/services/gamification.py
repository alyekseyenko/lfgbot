from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CompletionKind, LeaderboardPost, Lobby, LobbyCompletion, LobbyMember
from app.services.search_cooldown import LEAVE_REASON_KICKED

PORTUGAL = ZoneInfo("Europe/Lisbon")

ROLE_RECRUTA = "LFG Recruta"
ROLE_AGENTE = "LFG Agente"
ROLE_RADIANTE = "LFG Radiante"

LEVEL_NONE = "—"
LEVEL_RECRUTA = "Recruta"
LEVEL_AGENTE = "Agente"
LEVEL_RADIANTE = "Radiante"


@dataclass(frozen=True, slots=True)
class ProfileStats:
    level: str
    host_completions: int
    player_completions: int
    total_completions: int
    kicks_received: int
    next_level_hint: str


@dataclass(frozen=True, slots=True)
class RecentCompletion:
    mode: str
    kind: str
    awarded_at: datetime


@dataclass(frozen=True, slots=True)
class WeeklyEntry:
    user_id: int
    count: int


@dataclass(frozen=True, slots=True)
class CompletionAward:
    user_ids: list[int]


def level_from_counts(host_count: int, total: int) -> str:
    if total >= 20:
        return LEVEL_RADIANTE
    if host_count >= 3 or total >= 5:
        return LEVEL_AGENTE
    if total >= 1:
        return LEVEL_RECRUTA
    return LEVEL_NONE


def role_name_for_level(level: str) -> str | None:
    if level == LEVEL_RADIANTE:
        return ROLE_RADIANTE
    if level == LEVEL_AGENTE:
        return ROLE_AGENTE
    if level == LEVEL_RECRUTA:
        return ROLE_RECRUTA
    return None


def progress_bar(current: int, goal: int, width: int = 10) -> str:
    if goal <= 0:
        return "▱" * width
    ratio = min(1.0, max(0.0, current / goal))
    filled = int(round(ratio * width))
    return "▰" * filled + "▱" * (width - filled)


def level_progress_line(host_count: int, total: int) -> str:
    level = level_from_counts(host_count, total)
    if level == LEVEL_RADIANTE:
        return f"{progress_bar(10, 10)} nível máximo"
    if level == LEVEL_NONE:
        return f"{progress_bar(total, 1)} 1 grupo → Recruta"
    if level == LEVEL_RECRUTA:
        host_bar = f"{progress_bar(host_count, 3)} host ({host_count}/3)"
        total_bar = f"{progress_bar(total, 5)} total ({total}/5)"
        return f"{host_bar}\n{total_bar} · qualquer um chega a Agente"
    return f"{progress_bar(total, 20)} ({total}/20) → Radiante"


def next_level_hint(host_count: int, total: int) -> str:
    level = level_from_counts(host_count, total)
    if level == LEVEL_RADIANTE:
        return "Já atingiste o nível máximo."
    if level == LEVEL_NONE:
        return "Completa 1 grupo para seres Recruta."
    if level == LEVEL_RECRUTA:
        need_host = max(0, 3 - host_count)
        need_total = max(0, 5 - total)
        parts: list[str] = []
        if need_host > 0:
            parts.append(f"{need_host} como host")
        if need_total > 0:
            parts.append(f"{need_total} no total")
        return f"Para Agente: faltam {', '.join(parts)}."
    need_total = max(0, 20 - total)
    return f"Para Radiante: faltam {need_total} grupos completos."


def week_start_for_date(day: date) -> date:
    """Monday of the ISO week containing day (Lisbon calendar date)."""
    return day - timedelta(days=day.weekday())


def week_bounds_utc(week_start: date) -> tuple[datetime, datetime]:
    start_local = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=PORTUGAL
    )
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


async def record_lobby_completions(
    session: AsyncSession,
    lobby: Lobby,
    *,
    now: datetime,
) -> CompletionAward:
    settings = get_settings()
    if not settings.gamification_enabled:
        return CompletionAward(user_ids=[])

    min_age = timedelta(seconds=settings.completion_min_seconds)
    if now - lobby.created_at < min_age:
        return CompletionAward(user_ids=[])

    members_result = await session.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby.id,
            LobbyMember.left_at.is_(None),
        )
    )
    active_members = list(members_result.scalars())
    if len(active_members) < lobby.slots:
        return CompletionAward(user_ids=[])

    awarded_ids: list[int] = []
    rows: list[dict[str, object]] = []

    rows.append(
        {
            "lobby_id": lobby.id,
            "user_id": lobby.host_id,
            "kind": CompletionKind.host.value,
            "awarded_at": now,
        }
    )
    awarded_ids.append(lobby.host_id)

    for member in active_members:
        if now - member.joined_at < min_age:
            continue
        rows.append(
            {
                "lobby_id": lobby.id,
                "user_id": member.user_id,
                "kind": CompletionKind.player.value,
                "awarded_at": now,
            }
        )
        awarded_ids.append(member.user_id)

    if not rows:
        return CompletionAward(user_ids=[])

    stmt = insert(LobbyCompletion).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_lobby_completion")
    await session.execute(stmt)
    await session.flush()
    return CompletionAward(user_ids=awarded_ids)


async def recent_completions(
    session: AsyncSession, user_id: int, limit: int = 3
) -> list[RecentCompletion]:
    result = await session.execute(
        select(Lobby.mode, LobbyCompletion.kind, LobbyCompletion.awarded_at)
        .join(Lobby, LobbyCompletion.lobby_id == Lobby.id)
        .where(LobbyCompletion.user_id == user_id)
        .order_by(LobbyCompletion.awarded_at.desc())
        .limit(limit)
    )
    rows: list[RecentCompletion] = []
    for mode, kind, awarded_at in result.all():
        rows.append(
            RecentCompletion(
                mode=str(mode),
                kind=str(kind),
                awarded_at=awarded_at,
            )
        )
    return rows


async def last_completion_at(session: AsyncSession, user_id: int) -> datetime | None:
    result = await session.execute(
        select(func.max(LobbyCompletion.awarded_at)).where(LobbyCompletion.user_id == user_id)
    )
    value = result.scalar_one_or_none()
    return value if isinstance(value, datetime) else None


async def profile_stats(session: AsyncSession, user_id: int) -> ProfileStats:
    host_result = await session.execute(
        select(func.count())
        .select_from(LobbyCompletion)
        .where(
            LobbyCompletion.user_id == user_id,
            LobbyCompletion.kind == CompletionKind.host.value,
        )
    )
    player_result = await session.execute(
        select(func.count())
        .select_from(LobbyCompletion)
        .where(
            LobbyCompletion.user_id == user_id,
            LobbyCompletion.kind == CompletionKind.player.value,
        )
    )
    host_count = int(host_result.scalar_one())
    player_count = int(player_result.scalar_one())
    total = host_count + player_count

    kicks_result = await session.execute(
        select(func.count())
        .select_from(LobbyMember)
        .where(
            LobbyMember.user_id == user_id,
            LobbyMember.leave_reason == LEAVE_REASON_KICKED,
        )
    )
    kicks = int(kicks_result.scalar_one())

    level = level_from_counts(host_count, total)
    return ProfileStats(
        level=level,
        host_completions=host_count,
        player_completions=player_count,
        total_completions=total,
        kicks_received=kicks,
        next_level_hint=next_level_hint(host_count, total),
    )


async def weekly_top_hosts(
    session: AsyncSession, week_start: date, limit: int = 5
) -> list[WeeklyEntry]:
    start_utc, end_utc = week_bounds_utc(week_start)
    result = await session.execute(
        select(LobbyCompletion.user_id, func.count())
        .where(
            LobbyCompletion.kind == CompletionKind.host.value,
            LobbyCompletion.awarded_at >= start_utc,
            LobbyCompletion.awarded_at < end_utc,
        )
        .group_by(LobbyCompletion.user_id)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [WeeklyEntry(user_id=int(row[0]), count=int(row[1])) for row in result.all()]


async def weekly_top_players(
    session: AsyncSession, week_start: date, limit: int = 5
) -> list[WeeklyEntry]:
    start_utc, end_utc = week_bounds_utc(week_start)
    result = await session.execute(
        select(LobbyCompletion.user_id, func.count())
        .where(
            LobbyCompletion.kind == CompletionKind.player.value,
            LobbyCompletion.awarded_at >= start_utc,
            LobbyCompletion.awarded_at < end_utc,
        )
        .group_by(LobbyCompletion.user_id)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [WeeklyEntry(user_id=int(row[0]), count=int(row[1])) for row in result.all()]


async def leaderboard_already_posted(
    session: AsyncSession, week_start: date, channel_id: int
) -> bool:
    result = await session.execute(
        select(LeaderboardPost).where(
            LeaderboardPost.week_start == week_start,
            LeaderboardPost.channel_id == channel_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def save_leaderboard_post(
    session: AsyncSession,
    *,
    week_start: date,
    channel_id: int,
    message_id: int,
) -> None:
    session.add(
        LeaderboardPost(
            week_start=week_start,
            channel_id=channel_id,
            message_id=message_id,
        )
    )
    await session.flush()


def format_weekly_leaderboard(
    week_start: date,
    hosts: list[WeeklyEntry],
    players: list[WeeklyEntry],
    name_for_id: dict[int, str],
) -> str:
    week_end = week_start + timedelta(days=6)
    lines = [
        f"**Ranking LFG** ({week_start.isoformat()} a {week_end.isoformat()})",
        "",
        "**Top hosts**",
    ]
    if not hosts:
        lines.append("—")
    else:
        for i, entry in enumerate(hosts, start=1):
            name = name_for_id.get(entry.user_id, str(entry.user_id))
            lines.append(f"{i}. {name} — {entry.count}")
    lines.append("")
    lines.append("**Top jogadores**")
    if not players:
        lines.append("—")
    else:
        for i, entry in enumerate(players, start=1):
            name = name_for_id.get(entry.user_id, str(entry.user_id))
            lines.append(f"{i}. {name} — {entry.count}")
    return "\n".join(lines)
