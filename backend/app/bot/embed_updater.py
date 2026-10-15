import asyncio
import logging
from uuid import UUID

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embeds import (
    allowed_mentions_for_roles,
    build_lobby_embed,
    lobby_view_enabled,
)
from app.bot.views import LobbyView
from app.core.config import Settings
from app.core.events import DomainEvent, EventBus, EventType
from app.db.models import Lobby, LobbyState
from app.services.lobbies import get_lobby_detail

logger = logging.getLogger(__name__)

UPDATE_EVENTS = {
    EventType.lobby_created,
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
        self._lock = asyncio.Lock()

    def schedule(self, lobby_id: UUID) -> None:
        self._pending.add(lobby_id)

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
    ) -> None:
        self._bot: discord.Client | None = None
        self._settings = settings
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._debouncer = EmbedUpdateDebouncer(settings.embed_debounce_seconds)
        self._task: asyncio.Task[None] | None = None

    def set_bot(self, bot: discord.Client) -> None:
        self._bot = bot

    def attach(self) -> None:
        self._event_bus.subscribe(self._on_event)

    async def _on_event(self, event: DomainEvent) -> None:
        if event.type in UPDATE_EVENTS:
            self._debouncer.schedule(event.lobby_id)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._debouncer.interval_seconds)
            batch = await self._debouncer.drain()
            if not batch:
                continue
            for lobby_id in batch:
                try:
                    await self._refresh_message(lobby_id)
                except Exception:
                    logger.exception("failed to refresh embed for lobby %s", lobby_id)

    async def refresh_now(self, lobby_id: UUID) -> None:
        await self._refresh_message(lobby_id)

    async def _refresh_message(self, lobby_id: UUID) -> None:
        async with self._session_factory() as session:
            lobby = await get_lobby_detail(session, lobby_id)

        if lobby.channel_id is None or lobby.message_id is None:
            return

        if self._bot is None:
            return

        channel = self._bot.get_channel(lobby.channel_id)
        if channel is None:
            try:
                channel = await self._bot.fetch_channel(lobby.channel_id)
            except discord.HTTPException:
                logger.warning("channel %s not found for lobby %s", lobby.channel_id, lobby_id)
                return

        if not isinstance(channel, discord.abc.Messageable):
            return

        try:
            message = await channel.fetch_message(lobby.message_id)
        except discord.NotFound:
            logger.info("message %s missing for lobby %s", lobby.message_id, lobby_id)
            return
        except discord.HTTPException:
            logger.exception("discord error fetching message %s", lobby.message_id)
            return

        if lobby.state == LobbyState.expired:
            await self._handle_expired(message, lobby)
            return

        guild = message.guild
        thumb = self._settings.embed_thumbnail_url.strip() or None
        built = build_lobby_embed(lobby, guild=guild, thumbnail_url=thumb)
        view: LobbyView | None = None
        if lobby_view_enabled(lobby):
            active = [m for m in lobby.members if m.left_at is None]
            free = max(0, lobby.slots - len(active))
            view = LobbyView(lobby.id)
            view.bind(self._session_factory, self._event_bus)
            view.refresh_buttons(lobby.state.value, free)

        try:
            await message.edit(
                embed=built.embed,
                view=view,
                allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
            )
        except discord.HTTPException:
            logger.exception("failed to edit message %s", lobby.message_id)

    async def _handle_expired(self, message: discord.Message, lobby: Lobby) -> None:
        if self._settings.expired_mode == "delete":
            try:
                await message.delete()
            except discord.HTTPException:
                logger.exception("failed to delete expired message %s", message.id)
            return

        thumb = self._settings.embed_thumbnail_url.strip() or None
        built = build_lobby_embed(lobby, guild=message.guild, thumbnail_url=thumb)
        try:
            await message.edit(
                embed=built.embed,
                view=None,
                allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
            )
        except discord.HTTPException:
            logger.exception("failed to mark expired message %s", message.id)
