import asyncio
import logging
import time
from uuid import UUID

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embeds import (
    allowed_mentions_for_roles,
    build_lobby_embed,
    lobby_view_enabled,
)
from app.bot.members import fetch_guild_member
from app.bot.views import LobbyView, make_lobby_view
from app.core.config import Settings
from app.core.events import DomainEvent, EventBus, EventType
from app.core.metrics import discord_http_errors_total, embed_edits_total, embed_events_total
from app.db.models import Lobby, LobbyState
from app.services.guild_config import GuildConfigService
from app.services.lfg_embed_style import lobby_embed_style_for_post
from app.services.lobbies import get_lobby_detail

logger = logging.getLogger(__name__)

HOST_MEMBER_CACHE_TTL_SECONDS = 600.0
_REFRESH_CONCURRENCY = 4

UPDATE_EVENTS = {
    EventType.member_joined,
    EventType.member_left,
    EventType.lobby_full,
    EventType.lobby_opened,
    EventType.lobby_closed,
    EventType.lobby_expired,
    EventType.lobby_updated,
}


class EmbedUpdateDebouncer:
    def __init__(self, interval_seconds: float) -> None:
        self._interval = interval_seconds
        self._pending: set[UUID] = set()
        self._last_edit_at: dict[UUID, float] = {}
        self._lock = asyncio.Lock()

    def schedule(self, lobby_id: UUID) -> bool:
        """Return True when the embed may be refreshed immediately (leading edge)."""
        now = time.monotonic()
        last = self._last_edit_at.get(lobby_id)
        if last is None or (now - last) >= self._interval:
            return True
        self._pending.add(lobby_id)
        return False

    def mark_edited(self, lobby_id: UUID) -> None:
        self._last_edit_at[lobby_id] = time.monotonic()

    async def drain(self) -> set[UUID]:
        async with self._lock:
            batch = set(self._pending)
            self._pending.clear()
        return batch

    @property
    def interval_seconds(self) -> float:
        return self._interval


class EmbedUpdater:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        guild_config: GuildConfigService,
    ) -> None:
        self._bot: discord.Client | None = None
        self._settings = settings
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._guild_config = guild_config
        self._debouncer = EmbedUpdateDebouncer(settings.embed_debounce_seconds)
        self._task: asyncio.Task[None] | None = None
        self._host_member_cache: dict[tuple[int, int], tuple[discord.Member | None, float]] = {}
        self._refresh_sem = asyncio.Semaphore(_REFRESH_CONCURRENCY)

    def set_bot(self, bot: discord.Client) -> None:
        self._bot = bot

    def seed_host_member(self, guild_id: int, member: discord.Member) -> None:
        expires = time.monotonic() + HOST_MEMBER_CACHE_TTL_SECONDS
        self._host_member_cache[(guild_id, member.id)] = (member, expires)

    def attach(self) -> None:
        self._event_bus.subscribe(self._on_event)

    async def _on_event(self, event: DomainEvent) -> None:
        if event.type not in UPDATE_EVENTS:
            return
        embed_events_total.inc()
        lobby_id = event.lobby_id
        if self._debouncer.schedule(lobby_id):
            asyncio.create_task(
                self._refresh_and_mark(lobby_id),
                name=f"embed-refresh-{lobby_id}",
            )

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._debouncer.interval_seconds)
            batch = await self._debouncer.drain()
            if not batch:
                continue
            await asyncio.gather(
                *(self._refresh_and_mark(lobby_id) for lobby_id in batch),
                return_exceptions=True,
            )

    async def refresh_now(self, lobby_id: UUID) -> None:
        await self._refresh_and_mark(lobby_id)

    async def shutdown(self) -> None:
        batch = await self._debouncer.drain()
        for lobby_id in batch:
            await self._refresh_and_mark(lobby_id)

    async def _refresh_and_mark(self, lobby_id: UUID) -> None:
        async with self._refresh_sem:
            try:
                edited = await self._refresh_message(lobby_id)
            except Exception:
                logger.exception("failed to refresh embed for lobby %s", lobby_id)
                return
        if edited:
            self._debouncer.mark_edited(lobby_id)

    async def _get_host_member(
        self, guild: discord.Guild, discord_id: int
    ) -> discord.Member | None:
        key = (guild.id, discord_id)
        now = time.monotonic()
        cached = self._host_member_cache.get(key)
        if cached is not None and cached[1] > now:
            return cached[0]
        member = await fetch_guild_member(guild, discord_id)
        self._host_member_cache[key] = (member, now + HOST_MEMBER_CACHE_TTL_SECONDS)
        return member

    async def _resolve_messageable(
        self, channel_id: int, lobby_id: UUID
    ) -> discord.abc.Messageable | None:
        if self._bot is None:
            return None
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self._bot.fetch_channel(channel_id)
            except discord.HTTPException:
                logger.warning("channel %s not found for lobby %s", channel_id, lobby_id)
                return None
        if not isinstance(channel, discord.abc.Messageable):
            return None
        return channel

    async def _refresh_message(self, lobby_id: UUID) -> bool:
        async with self._session_factory() as session:
            lobby = await get_lobby_detail(session, lobby_id)

        if lobby.channel_id is None or lobby.message_id is None:
            return False

        channel = await self._resolve_messageable(lobby.channel_id, lobby_id)
        if channel is None:
            return False

        guild: discord.Guild | None = None
        if isinstance(channel, discord.abc.GuildChannel):
            guild = channel.guild

        message = channel.get_partial_message(lobby.message_id)

        if lobby.state == LobbyState.expired:
            return await self._handle_expired(message, lobby, guild)

        thumb = self._settings.embed_thumbnail_url.strip() or None
        role_mappings: dict[tuple[str, str], int] | None = None
        embed_style = None
        if guild is not None:
            async with self._session_factory() as session:
                cfg = await self._guild_config.get_config(session, guild.id)
            role_mappings = cfg.role_mappings
            embed_style = lobby_embed_style_for_post(cfg, lobby.post_style)
        host_member = None
        if guild is not None:
            host_member = await self._get_host_member(guild, lobby.host.discord_id)
        built = build_lobby_embed(
            lobby,
            guild=guild,
            thumbnail_url=thumb,
            role_mappings=role_mappings,
            embed_style=embed_style,
            host_member=host_member,
        )
        view: LobbyView | None = None
        if lobby_view_enabled(lobby):
            active = [m for m in lobby.members if m.left_at is None]
            free = max(0, lobby.slots - len(active))
            view = make_lobby_view(lobby.id, lobby.post_style)
            view.bind(self._session_factory, self._event_bus, self._guild_config)
            view.refresh_buttons(lobby.state.value, free)

        try:
            await message.edit(
                embed=built.embed,
                view=view,
                allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
            )
            embed_edits_total.inc()
            return True
        except discord.NotFound:
            logger.info("message %s missing for lobby %s", lobby.message_id, lobby_id)
            return False
        except discord.HTTPException as exc:
            discord_http_errors_total.labels(status=str(exc.status)).inc()
            logger.exception("failed to edit message %s", lobby.message_id)
            return False

    async def _handle_expired(
        self,
        message: discord.PartialMessage,
        lobby: Lobby,
        guild: discord.Guild | None,
    ) -> bool:
        if self._settings.expired_mode == "delete":
            try:
                await message.delete()
                embed_edits_total.inc()
                return True
            except discord.NotFound:
                logger.info("message %s missing for expired lobby %s", message.id, lobby.id)
                return False
            except discord.HTTPException:
                logger.exception("failed to delete expired message %s", message.id)
                return False

        thumb = self._settings.embed_thumbnail_url.strip() or None
        role_mappings: dict[tuple[str, str], int] | None = None
        embed_style = None
        if guild is not None:
            async with self._session_factory() as session:
                cfg = await self._guild_config.get_config(session, guild.id)
            role_mappings = cfg.role_mappings
            embed_style = lobby_embed_style_for_post(cfg, lobby.post_style)
        host_member = None
        if guild is not None:
            host_member = await self._get_host_member(guild, lobby.host.discord_id)
        built = build_lobby_embed(
            lobby,
            guild=guild,
            thumbnail_url=thumb,
            role_mappings=role_mappings,
            embed_style=embed_style,
            host_member=host_member,
        )
        try:
            await message.edit(
                embed=built.embed,
                view=None,
                allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
            )
            embed_edits_total.inc()
            return True
        except discord.NotFound:
            logger.info("message %s missing for expired lobby %s", message.id, lobby.id)
            return False
        except discord.HTTPException:
            logger.exception("failed to mark expired message %s", message.id)
            return False
