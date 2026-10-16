from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.domain_event_session import queue_domain_event
from app.core.events import DomainEvent, EventBus, EventType
from app.core.metrics import joins_total, lobbies_created_total, observe_lobby_filled
from app.db.models import Lobby, LobbyMember, LobbyState, User
from app.services.agents import (
    applicant_matches_wanted,
    parse_wanted_agents_csv,
    serialize_wanted_agents,
)
from app.services.errors import (
    LobbyEditError,
    LobbyFullError,
    LobbyNotFoundError,
    LobbyNotJoinableError,
    NotInLobbyError,
    RankRangeError,
)
from app.services.gamification import record_lobby_completions
from app.services.host_recreate_cooldown import (
    apply_host_recreate_cooldown,
    assert_can_host_create,
)
from app.services.lobby_patch import UNSET, LobbyHostPatch
from app.services.lobby_post_style import POST_STYLE_INTERACTIVE, normalize_post_style
from app.services.lobby_source import LOBBY_SOURCE_UNKNOWN, normalize_lobby_source
from app.services.party_code import (
    assert_party_code_available_for_guild,
    normalize_party_code,
)
from app.services.ranks import rank_fits_lobby, validate_rank_range
from app.services.search_cooldown import (
    LEAVE_REASON_KICKED,
    LEAVE_REASON_LEFT,
    SearchCooldownPolicy,
    apply_private_voluntary_leave_penalty,
    assert_can_search,
)
from app.services.users import upsert_user


async def _active_member_count(session: AsyncSession, lobby_id: UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(LobbyMember)
        .where(LobbyMember.lobby_id == lobby_id, LobbyMember.left_at.is_(None))
    )
    return int(result.scalar_one())


async def _get_user_for_update(session: AsyncSession, discord_id: int) -> User:
    result = await session.execute(
        select(User).where(User.discord_id == discord_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise LobbyNotJoinableError("Utilizador não registado.")
    return user


async def _get_lobby_for_update(session: AsyncSession, lobby_id: UUID) -> Lobby:
    result = await session.execute(select(Lobby).where(Lobby.id == lobby_id).with_for_update())
    lobby = result.scalar_one_or_none()
    if lobby is None:
        raise LobbyNotFoundError(f"Lobby {lobby_id} not found")
    return lobby


def _mark_filled(lobby: Lobby, now: datetime) -> None:
    if lobby.filled_at is None:
        lobby.filled_at = now
        if lobby.created_at is not None:
            observe_lobby_filled(
                lobby.created_at.timestamp(),
                lobby.filled_at.timestamp(),
            )


def _mark_ended(lobby: Lobby, now: datetime) -> None:
    if lobby.ended_at is None:
        lobby.ended_at = now


def _ensure_joinable(lobby: Lobby, now: datetime) -> None:
    if lobby.state in (LobbyState.closed, LobbyState.expired):
        raise LobbyNotJoinableError("Este lobby já não está disponível.")
    if lobby.expires_at <= now:
        raise LobbyNotJoinableError("Este lobby expirou.")
    if lobby.state == LobbyState.full:
        raise LobbyFullError("Lobby cheio.")


async def create_lobby(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    host: User,
    mode: str,
    slots: int,
    party_code: str | None,
    expires_in: timedelta,
    min_rank: str | None = None,
    max_rank: str | None = None,
    party_code_public: bool = True,
    wanted_agents: list[str] | None = None,
    ranks_verified: bool = False,
    channel_id: int | None = None,
    message_id: int | None = None,
    discord_guild_id: int | None = None,
    create_source: str = LOBBY_SOURCE_UNKNOWN,
    post_style: str = POST_STYLE_INTERACTIVE,
) -> Lobby:
    if slots < 1 or slots > 4:
        raise ValueError("slots must be between 1 and 4")
    try:
        validate_rank_range(min_rank, max_rank)
    except RankRangeError:
        raise

    now = datetime.now(UTC)
    host_row = await _get_user_for_update(session, host.discord_id)
    assert_can_search(host_row, now)
    assert_can_host_create(host_row, now)

    normalized_code = normalize_party_code(party_code)
    if discord_guild_id is not None:
        await assert_party_code_available_for_guild(
            session,
            discord_guild_id=discord_guild_id,
            party_code=normalized_code,
            now=now,
        )

    lobby = Lobby(
        discord_guild_id=discord_guild_id,
        host_id=host.discord_id,
        mode=mode,
        slots=slots,
        party_code=normalized_code,
        party_code_public=party_code_public,
        wanted_agents=serialize_wanted_agents(wanted_agents or []),
        ranks_verified=ranks_verified,
        min_rank=min_rank,
        max_rank=max_rank,
        state=LobbyState.open,
        expires_at=now + expires_in,
        channel_id=channel_id,
        message_id=message_id,
        create_source=normalize_lobby_source(create_source),
        post_style=normalize_post_style(post_style),
    )
    session.add(lobby)
    await session.flush()
    lobbies_created_total.labels(source=lobby.create_source or "unknown").inc()
    queue_domain_event(session, DomainEvent(EventType.lobby_created, lobby.id))
    return lobby


async def set_lobby_message(
    session: AsyncSession, lobby_id: UUID, channel_id: int, message_id: int
) -> Lobby:
    lobby = await _get_lobby_for_update(session, lobby_id)
    lobby.channel_id = channel_id
    lobby.message_id = message_id
    await session.flush()
    return lobby


async def join_lobby(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    user: User,
    applicant_agents: frozenset[str] | None = None,
    now: datetime | None = None,
) -> LobbyMember:
    now = now or datetime.now(UTC)
    user = await _get_user_for_update(session, user.discord_id)
    assert_can_search(user, now)

    lobby = await _get_lobby_for_update(session, lobby_id)
    if normalize_post_style(lobby.post_style) == "simple":
        raise LobbyNotJoinableError("Este pedido é simples — entra no jogo pelo código.")
    _ensure_joinable(lobby, now)

    if user.discord_id == lobby.host_id:
        raise LobbyNotJoinableError("O host já está no grupo.")

    if lobby.ranks_verified and not rank_fits_lobby(user.rank, lobby.min_rank, lobby.max_rank):
        if lobby.min_rank and lobby.max_rank:
            band = f"{lobby.min_rank} – {lobby.max_rank}"
        elif lobby.min_rank:
            band = f"mínimo {lobby.min_rank}"
        else:
            band = f"máximo {lobby.max_rank}"
        raise LobbyNotJoinableError(
            f"Este lobby pede ranks {band} (o teu: {user.rank or 'sem rank'})."
        )

    wanted = parse_wanted_agents_csv(lobby.wanted_agents)
    if wanted and not applicant_matches_wanted(wanted, applicant_agents or frozenset()):
        raise LobbyNotJoinableError(f"Este lobby procura roles: {', '.join(wanted)}.")

    existing = await session.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.user_id == user.discord_id,
            LobbyMember.left_at.is_(None),
        )
    )
    member = existing.scalar_one_or_none()
    if member is not None:
        return member

    active = await _active_member_count(session, lobby_id)
    if active >= lobby.slots:
        lobby.state = LobbyState.full
        await session.flush()
        raise LobbyFullError("Lobby cheio.")

    member = LobbyMember(lobby_id=lobby_id, user_id=user.discord_id)
    session.add(member)
    await session.flush()
    joins_total.inc()

    active = await _active_member_count(session, lobby_id)
    if active >= lobby.slots:
        lobby.state = LobbyState.full
        _mark_filled(lobby, now)
        queue_domain_event(session, DomainEvent(EventType.lobby_full, lobby.id))
    else:
        queue_domain_event(
            session,
            DomainEvent(EventType.member_joined, lobby.id, {"user_id": user.discord_id}),
        )
    return member


async def leave_lobby(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    user: User,
    reason: str,
    now: datetime | None = None,
    search_cooldown_policy: SearchCooldownPolicy | None = None,
) -> None:
    now = now or datetime.now(UTC)
    lobby = await _get_lobby_for_update(session, lobby_id)

    if lobby.state in (LobbyState.closed, LobbyState.expired):
        raise LobbyNotJoinableError("Este lobby já não está ativo.")

    user = await _get_user_for_update(session, user.discord_id)

    result = await session.execute(
        select(LobbyMember).where(
            LobbyMember.lobby_id == lobby_id,
            LobbyMember.user_id == user.discord_id,
            LobbyMember.left_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotInLobbyError("Não estás neste lobby.")

    member.left_at = now
    member.leave_reason = reason
    was_full = lobby.state == LobbyState.full
    if was_full:
        lobby.state = LobbyState.open
        queue_domain_event(session, DomainEvent(EventType.lobby_opened, lobby.id))
    queue_domain_event(
        session,
        DomainEvent(
            EventType.member_left, lobby.id, {"user_id": user.discord_id, "reason": reason}
        ),
    )

    if reason == LEAVE_REASON_LEFT and not lobby.party_code_public:
        await apply_private_voluntary_leave_penalty(
            session, user, now, policy=search_cooldown_policy
        )


async def kick_member_as_host(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    host_id: int,
    target_user_id: int,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(UTC)
    lobby = await _get_lobby_for_update(session, lobby_id)
    if lobby.host_id != host_id:
        raise LobbyNotJoinableError("Só o host pode expulsar jogadores.")
    if target_user_id == host_id:
        raise LobbyNotJoinableError("Não podes expulsar-te a ti mesmo.")

    result = await session.execute(select(User).where(User.discord_id == target_user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise NotInLobbyError("Jogador não encontrado.")

    await leave_lobby(
        session,
        event_bus,
        lobby_id=lobby_id,
        user=target,
        reason=LEAVE_REASON_KICKED,
        now=now,
    )


async def close_lobby(
    session: AsyncSession, event_bus: EventBus, *, lobby_id: UUID, now: datetime | None = None
) -> Lobby:
    now = now or datetime.now(UTC)
    lobby = await _get_lobby_for_update(session, lobby_id)
    if lobby.state in (LobbyState.closed, LobbyState.expired):
        return lobby

    award = await record_lobby_completions(session, lobby, now=now)

    members = await session.execute(
        select(LobbyMember).where(LobbyMember.lobby_id == lobby_id, LobbyMember.left_at.is_(None))
    )
    for member in members.scalars():
        member.left_at = now
        member.leave_reason = "closed"

    lobby.state = LobbyState.closed
    _mark_ended(lobby, now)
    await session.flush()
    queue_domain_event(
        session,
        DomainEvent(
            EventType.lobby_closed,
            lobby.id,
            {"awarded_user_ids": award.user_ids},
        ),
    )
    return lobby


async def _sync_lobby_capacity_state(session: AsyncSession, lobby: Lobby) -> None:
    active = await _active_member_count(session, lobby.id)
    if active >= lobby.slots:
        lobby.state = LobbyState.full
    elif lobby.state == LobbyState.full:
        lobby.state = LobbyState.open


async def update_lobby_as_host(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    host_id: int,
    patch: LobbyHostPatch,
) -> Lobby:
    if patch.is_empty():
        raise LobbyEditError("Indica pelo menos um campo para alterar.")

    lobby = await _get_lobby_for_update(session, lobby_id)
    if lobby.host_id != host_id:
        raise LobbyNotJoinableError("Só o host pode editar este lobby.")
    if lobby.state in (LobbyState.closed, LobbyState.expired):
        raise LobbyNotJoinableError("Este lobby já não está ativo.")

    if patch.min_rank is UNSET:
        new_min = lobby.min_rank
    else:
        new_min = cast(str | None, patch.min_rank)
    if patch.max_rank is UNSET:
        new_max = lobby.max_rank
    else:
        new_max = cast(str | None, patch.max_rank)
    validate_rank_range(new_min, new_max)

    if patch.slots is not UNSET:
        slots = cast(int, patch.slots)
        if slots < 1 or slots > 4:
            raise LobbyEditError("Vagas tem de ser entre 1 e 4.")
        active = await _active_member_count(session, lobby.id)
        if active > slots:
            raise LobbyEditError(
                f"Já há {active} jogadores na lista; não podes baixar para {slots} vagas."
            )
        lobby.slots = slots

    if patch.min_rank is not UNSET:
        lobby.min_rank = cast(str | None, patch.min_rank)
    if patch.max_rank is not UNSET:
        lobby.max_rank = cast(str | None, patch.max_rank)
    if patch.party_code is not UNSET:
        now = datetime.now(UTC)
        normalized_code = normalize_party_code(cast(str | None, patch.party_code))
        if lobby.discord_guild_id is not None:
            await assert_party_code_available_for_guild(
                session,
                discord_guild_id=int(lobby.discord_guild_id),
                party_code=normalized_code,
                now=now,
                exclude_lobby_id=lobby.id,
            )
        lobby.party_code = normalized_code
    if patch.party_code_public is not UNSET:
        lobby.party_code_public = cast(bool, patch.party_code_public)
    if patch.wanted_agents is not UNSET:
        lobby.wanted_agents = serialize_wanted_agents(cast(list[str], patch.wanted_agents))
    if patch.ranks_verified is not UNSET:
        lobby.ranks_verified = cast(bool, patch.ranks_verified)

    await _sync_lobby_capacity_state(session, lobby)
    await session.flush()
    queue_domain_event(session, DomainEvent(EventType.lobby_updated, lobby.id))
    return lobby


async def close_lobby_as_host(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    host_id: int,
    now: datetime | None = None,
    host_recreate_cooldown: timedelta | None = None,
    apply_host_recreate_cooldown_on_close: bool = True,
) -> Lobby:
    now = now or datetime.now(UTC)
    lobby = await _get_lobby_for_update(session, lobby_id)
    if lobby.host_id != host_id:
        raise LobbyNotJoinableError("Só o host pode fechar este lobby.")
    closed = await close_lobby(session, event_bus, lobby_id=lobby_id, now=now)
    if apply_host_recreate_cooldown_on_close and host_recreate_cooldown is not None:
        host_row = await _get_user_for_update(session, host_id)
        apply_host_recreate_cooldown(host_row, now, host_recreate_cooldown)
    return closed


async def expire_due_lobbies(
    session: AsyncSession, event_bus: EventBus, *, now: datetime
) -> list[Lobby]:
    result = await session.execute(
        select(Lobby)
        .where(
            Lobby.state.in_((LobbyState.open, LobbyState.full)),
            Lobby.expires_at <= now,
        )
        .with_for_update()
    )
    lobbies = list(result.scalars())
    expired: list[Lobby] = []

    for lobby in lobbies:
        award = await record_lobby_completions(session, lobby, now=now)

        members = await session.execute(
            select(LobbyMember).where(
                LobbyMember.lobby_id == lobby.id, LobbyMember.left_at.is_(None)
            )
        )
        for member in members.scalars():
            member.left_at = now
            member.leave_reason = "expired"
        lobby.state = LobbyState.expired
        _mark_ended(lobby, now)
        expired.append(lobby)
        queue_domain_event(
            session,
            DomainEvent(
                EventType.lobby_expired,
                lobby.id,
                {"awarded_user_ids": award.user_ids},
            ),
        )

    if expired:
        await session.flush()
    return expired


async def get_lobby_detail(session: AsyncSession, lobby_id: UUID) -> Lobby:
    result = await session.execute(
        select(Lobby)
        .where(Lobby.id == lobby_id)
        .options(
            selectinload(Lobby.host),
            selectinload(Lobby.members).selectinload(LobbyMember.user),
        )
    )
    lobby = result.scalar_one_or_none()
    if lobby is None:
        raise LobbyNotFoundError(f"Lobby {lobby_id} not found")
    return lobby


async def get_host_active_lobby(
    session: AsyncSession,
    host_id: int,
    now: datetime | None = None,
) -> Lobby | None:
    """Lobby aberto/cheio do host que ainda não expirou (hora em expires_at)."""
    if now is None:
        now = datetime.now(UTC)
    result = await session.execute(
        select(Lobby)
        .where(
            Lobby.host_id == host_id,
            Lobby.state.in_((LobbyState.open, LobbyState.full)),
            Lobby.expires_at > now,
        )
        .order_by(Lobby.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def host_has_open_lobby(session: AsyncSession, host_id: int) -> bool:
    return await get_host_active_lobby(session, host_id) is not None


async def list_active_lobbies(session: AsyncSession) -> list[Lobby]:
    result = await session.execute(
        select(Lobby)
        .where(Lobby.state.in_((LobbyState.open, LobbyState.full)))
        .options(
            selectinload(Lobby.host), selectinload(Lobby.members).selectinload(LobbyMember.user)
        )
    )
    return list(result.scalars())


async def ensure_user_and_join(
    session: AsyncSession,
    event_bus: EventBus,
    *,
    lobby_id: UUID,
    discord_id: int,
    name: str,
) -> LobbyMember:
    user = await upsert_user(session, discord_id, name)
    return await join_lobby(session, event_bus, lobby_id=lobby_id, user=user)
