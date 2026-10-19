from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Guild, GuildCreatorLevel, Lobby
from app.services.gamification import PORTUGAL, week_bounds_utc

MAX_CREATOR_LEVELS = 12

DEFAULT_CREATOR_LEVELS: tuple[tuple[int, str, int], ...] = (
    (1, "Recruta", 1),
    (2, "Anfitrião", 5),
    (3, "Organizador", 15),
    (4, "Veterano", 40),
    (5, "Lenda", 100),
)


@dataclass(frozen=True, slots=True)
class CreatorLevelDef:
    level_number: int
    name: str
    min_rooms: int
    discord_role_id: int | None = None


@dataclass(frozen=True, slots=True)
class CreatorProgress:
    rooms_created: int
    current: CreatorLevelDef | None
    next_level: CreatorLevelDef | None

    @property
    def level_name(self) -> str:
        return self.current.name if self.current is not None else "—"

    @property
    def level_number(self) -> int:
        return self.current.level_number if self.current is not None else 0

    @property
    def next_level_hint(self) -> str:
        if self.current is None and self.next_level is not None:
            need = max(0, self.next_level.min_rooms - self.rooms_created)
            return f"Cria {need} grupo{'s' if need != 1 else ''} para seres {self.next_level.name}."
        if self.next_level is None:
            return "Já atingiste o nível máximo de criador."
        need = max(0, self.next_level.min_rooms - self.rooms_created)
        return (
            f"Para {self.next_level.name}: faltam {need} "
            f"grupo{'s' if need != 1 else ''} criado{'s' if need != 1 else ''}."
        )


@dataclass(frozen=True, slots=True)
class CreatorLeaderboardEntry:
    user_id: int
    count: int


def default_creator_levels() -> list[CreatorLevelDef]:
    return [
        CreatorLevelDef(level_number=n, name=name, min_rooms=rooms)
        for n, name, rooms in DEFAULT_CREATOR_LEVELS
    ]


def row_to_def(row: GuildCreatorLevel) -> CreatorLevelDef:
    role_id = int(row.discord_role_id) if row.discord_role_id else None
    if role_id is not None and role_id <= 0:
        role_id = None
    return CreatorLevelDef(
        level_number=int(row.level_number),
        name=str(row.name),
        min_rooms=int(row.min_rooms),
        discord_role_id=role_id,
    )


def anchor_week_start_for_date(anchor: date, day: date) -> date | None:
    """Início da semana de 7 dias que contém ``day``, contando a partir de ``anchor``."""
    if day < anchor:
        return None
    period_index = (day - anchor).days // 7
    return anchor + timedelta(days=period_index * 7)


def anchor_week_end_date(week_start: date) -> date:
    return week_start + timedelta(days=6)


def completed_anchor_week_to_post(now_pt: datetime, anchor: date) -> date | None:
    """Semana âncora que acabou de fechar (21:00 de Lisboa no último dia da semana)."""
    if now_pt.tzinfo is None:
        now_pt = now_pt.replace(tzinfo=PORTUGAL)
    else:
        now_pt = now_pt.astimezone(PORTUGAL)
    if now_pt.hour != 21:
        return None
    week_start = anchor_week_start_for_date(anchor, now_pt.date())
    if week_start is None:
        return None
    if now_pt.date() != anchor_week_end_date(week_start):
        return None
    return week_start


def creator_level_number(progress: CreatorProgress) -> int:
    return progress.current.level_number if progress.current is not None else 0


def did_creator_level_up(
    rooms_before: int,
    rooms_after: int,
    levels: list[CreatorLevelDef],
) -> tuple[bool, CreatorProgress, CreatorProgress]:
    before = resolve_creator_progress(rooms_before, levels)
    after = resolve_creator_progress(rooms_after, levels)
    return creator_level_number(after) > creator_level_number(before), after, before


def creator_role_ids_for_levels(levels: list[CreatorLevelDef]) -> tuple[int, ...]:
    ids: list[int] = []
    for item in levels:
        if item.discord_role_id is not None and item.discord_role_id > 0:
            ids.append(item.discord_role_id)
    return tuple(sorted(set(ids)))


def resolve_creator_progress(
    rooms_created: int,
    levels: list[CreatorLevelDef],
) -> CreatorProgress:
    ordered = sorted(levels, key=lambda item: (item.min_rooms, item.level_number))
    current: CreatorLevelDef | None = None
    nxt: CreatorLevelDef | None = None
    for item in ordered:
        if rooms_created >= item.min_rooms:
            current = item
        elif nxt is None:
            nxt = item
            break
    return CreatorProgress(rooms_created=rooms_created, current=current, next_level=nxt)


def normalize_level_payload(raw: list[dict[str, object]]) -> list[CreatorLevelDef]:
    if len(raw) > MAX_CREATOR_LEVELS:
        raise ValueError(f"Máximo de {MAX_CREATOR_LEVELS} níveis.")
    seen_numbers: set[int] = set()
    out: list[CreatorLevelDef] = []
    for index, item in enumerate(raw, start=1):
        try:
            number = int(item.get("level_number") or index)
            min_rooms = int(item.get("min_rooms") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("level_number e min_rooms têm de ser números.") from exc
        name = str(item.get("name") or "").strip()[:64]
        if not name:
            raise ValueError("Cada nível precisa de um nome.")
        if number < 1 or number > 20:
            raise ValueError("O número do nível tem de estar entre 1 e 20.")
        if min_rooms < 0:
            raise ValueError("min_rooms não pode ser negativo.")
        if number in seen_numbers:
            raise ValueError("Há números de nível repetidos.")
        seen_numbers.add(number)
        role_raw = item.get("discord_role_id")
        role_id: int | None = None
        if role_raw not in (None, "", 0, "0"):
            try:
                role_id = int(role_raw)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ValueError("discord_role_id inválido.") from exc
            if role_id <= 0:
                role_id = None
        out.append(
            CreatorLevelDef(
                level_number=number,
                name=name,
                min_rooms=min_rooms,
                discord_role_id=role_id,
            )
        )
    out.sort(key=lambda item: item.level_number)
    return out


async def list_creator_levels(
    session: AsyncSession, discord_guild_id: int
) -> list[CreatorLevelDef]:
    result = await session.execute(
        select(GuildCreatorLevel)
        .where(GuildCreatorLevel.discord_guild_id == discord_guild_id)
        .order_by(GuildCreatorLevel.level_number.asc())
    )
    return [row_to_def(row) for row in result.scalars()]


async def ensure_default_creator_levels(
    session: AsyncSession, discord_guild_id: int
) -> list[CreatorLevelDef]:
    existing = await list_creator_levels(session, discord_guild_id)
    if existing:
        return existing
    guild = await session.get(Guild, discord_guild_id)
    if guild is None:
        return default_creator_levels()
    for item in default_creator_levels():
        session.add(
            GuildCreatorLevel(
                discord_guild_id=discord_guild_id,
                level_number=item.level_number,
                name=item.name,
                min_rooms=item.min_rooms,
                discord_role_id=None,
            )
        )
    await session.flush()
    return await list_creator_levels(session, discord_guild_id)


async def replace_creator_levels(
    session: AsyncSession,
    discord_guild_id: int,
    levels: list[CreatorLevelDef],
) -> list[CreatorLevelDef]:
    await session.execute(
        delete(GuildCreatorLevel).where(
            GuildCreatorLevel.discord_guild_id == discord_guild_id
        )
    )
    for item in levels:
        session.add(
            GuildCreatorLevel(
                discord_guild_id=discord_guild_id,
                level_number=item.level_number,
                name=item.name,
                min_rooms=item.min_rooms,
                discord_role_id=item.discord_role_id,
            )
        )
    await session.flush()
    return await list_creator_levels(session, discord_guild_id)


async def count_rooms_created(
    session: AsyncSession,
    host_id: int,
    *,
    discord_guild_id: int | None = None,
) -> int:
    stmt = select(func.count()).select_from(Lobby).where(Lobby.host_id == host_id)
    if discord_guild_id is not None:
        stmt = stmt.where(Lobby.discord_guild_id == discord_guild_id)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def weekly_top_creators_in_anchor_week(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    week_start: date,
    limit: int = 10,
) -> list[CreatorLeaderboardEntry]:
    start_utc, end_utc = week_bounds_utc(week_start)
    result = await session.execute(
        select(Lobby.host_id, func.count())
        .where(
            Lobby.discord_guild_id == discord_guild_id,
            Lobby.created_at >= start_utc,
            Lobby.created_at < end_utc,
        )
        .group_by(Lobby.host_id)
        .order_by(func.count().desc(), Lobby.host_id.asc())
        .limit(limit)
    )
    return [
        CreatorLeaderboardEntry(user_id=int(row[0]), count=int(row[1]))
        for row in result.all()
    ]


async def all_time_top_creators(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[CreatorLeaderboardEntry]:
    result = await session.execute(
        select(Lobby.host_id, func.count())
        .where(Lobby.discord_guild_id == discord_guild_id)
        .group_by(Lobby.host_id)
        .order_by(func.count().desc(), Lobby.host_id.asc())
        .offset(max(0, offset))
        .limit(limit)
    )
    return [
        CreatorLeaderboardEntry(user_id=int(row[0]), count=int(row[1]))
        for row in result.all()
    ]
