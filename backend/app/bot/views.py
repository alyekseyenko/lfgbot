from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.discord_roles import extract_agents_from_member
from app.bot.members import upsert_user_from_member
from app.core.events import EventBus
from app.db.models import Lobby, User
from app.services import lobbies as lobby_service
from app.services.errors import (
    LobbyFullError,
    LobbyNotFoundError,
    LobbyNotJoinableError,
    NotInLobbyError,
    SearchBlockedError,
)
from app.services.search_cooldown import format_search_blocked_until

logger = logging.getLogger(__name__)


def join_custom_id(lobby_id: UUID) -> str:
    return f"lfg:join:{lobby_id}"


def leave_custom_id(lobby_id: UUID) -> str:
    return f"lfg:leave:{lobby_id}"


def close_custom_id(lobby_id: UUID) -> str:
    return f"lfg:close:{lobby_id}"


def kick_custom_id(lobby_id: UUID) -> str:
    return f"lfg:kick:{lobby_id}"


def parse_lobby_id_from_custom_id(custom_id: str) -> UUID | None:
    parts = custom_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "lfg":
        return None
    try:
        return UUID(parts[2])
    except ValueError:
        return None


def _join_success_message(lobby: Lobby, party_code: str | None) -> str:
    if party_code and not lobby.party_code_public:
        return (
            "Entraste no lobby.\n"
            f"**Código da party:**\n```{party_code}```"
        )
    return "Entraste no lobby."


class KickMemberSelect(discord.ui.Select):
    def __init__(
        self,
        lobby_id: UUID,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        options: list[discord.SelectOption],
    ) -> None:
        super().__init__(
            placeholder="Escolhe quem expulsar",
            min_values=1,
            max_values=1,
            options=options,
        )
        self._lobby_id = lobby_id
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user is None:
            return
        target_id = int(self.values[0])
        await interaction.response.defer(ephemeral=True)
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await lobby_service.kick_member_as_host(
                        session,
                        self._event_bus,
                        lobby_id=self._lobby_id,
                        host_id=interaction.user.id,
                        target_user_id=target_id,
                    )
        except (LobbyNotJoinableError, NotInLobbyError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("kick failed in lobby %s", self._lobby_id)
            await interaction.followup.send(
                "Não foi possível expulsar o jogador.", ephemeral=True
            )
            return
        await interaction.followup.send("Jogador expulso do lobby.", ephemeral=True)


class KickMemberView(discord.ui.View):
    def __init__(
        self,
        lobby_id: UUID,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        members: list[tuple[int, str]],
    ) -> None:
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(label=name[:100], value=str(user_id))
            for user_id, name in members[:25]
        ]
        self.add_item(KickMemberSelect(lobby_id, session_factory, event_bus, options))


class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: UUID) -> None:
        super().__init__(timeout=None)
        self.lobby_id = lobby_id
        join_btn = discord.ui.Button(
            label="Entrar",
            style=discord.ButtonStyle.success,
            custom_id=join_custom_id(lobby_id),
            row=0,
        )
        leave_btn = discord.ui.Button(
            label="Sair",
            style=discord.ButtonStyle.secondary,
            custom_id=leave_custom_id(lobby_id),
            row=0,
        )
        kick_btn = discord.ui.Button(
            label="Expulsar",
            style=discord.ButtonStyle.secondary,
            custom_id=kick_custom_id(lobby_id),
            row=0,
        )
        close_btn = discord.ui.Button(
            label="Fechar",
            style=discord.ButtonStyle.danger,
            custom_id=close_custom_id(lobby_id),
            row=0,
        )
        join_btn.callback = self._join_callback
        leave_btn.callback = self._leave_callback
        close_btn.callback = self._close_callback
        kick_btn.callback = self._kick_callback
        self.add_item(join_btn)
        self.add_item(leave_btn)
        self.add_item(kick_btn)
        self.add_item(close_btn)
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._event_bus: EventBus | None = None

    def bind(self, session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def _join_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_join(interaction)

    async def _leave_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_leave(interaction)

    async def _close_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_close(interaction)

    async def _kick_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_kick_prompt(interaction)

    async def _handle_join(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message("Bot em arranque. Tenta outra vez.", ephemeral=True)
            return
        if interaction.user is None:
            return

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    if not isinstance(interaction.user, discord.Member):
                        await interaction.response.send_message(
                            "Só podes entrar dentro do servidor.", ephemeral=True
                        )
                        return
                    user = await upsert_user_from_member(session, interaction.user)
                    agents = frozenset(extract_agents_from_member(interaction.user))
                    await lobby_service.join_lobby(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        user=user,
                        applicant_agents=agents,
                    )
        except SearchBlockedError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except LobbyFullError:
            await interaction.response.send_message("Lobby cheio.", ephemeral=True)
            return
        except LobbyNotJoinableError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        async with self._session_factory() as session:
            lobby = await lobby_service.get_lobby_detail(session, self.lobby_id)
        await interaction.response.send_message(
            _join_success_message(lobby, lobby.party_code),
            ephemeral=True,
        )

    async def _handle_leave(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message("Bot em arranque. Tenta outra vez.", ephemeral=True)
            return
        if interaction.user is None:
            return

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    if not isinstance(interaction.user, discord.Member):
                        await interaction.response.send_message(
                            "Só podes sair dentro do servidor.", ephemeral=True
                        )
                        return
                    user = await upsert_user_from_member(session, interaction.user)
                    await lobby_service.leave_lobby(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        user=user,
                        reason="left",
                    )
        except NotInLobbyError:
            await interaction.response.send_message("Não estás neste lobby.", ephemeral=True)
            return
        except LobbyNotJoinableError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        message = "Saíste do lobby."
        async with self._session_factory() as session:
            result = await session.execute(
                select(User).where(User.discord_id == interaction.user.id)
            )
            user_row = result.scalar_one_or_none()
            now = datetime.now(UTC)
            if (
                user_row is not None
                and user_row.search_blocked_until is not None
                and user_row.search_blocked_until > now
            ):
                message = f"{message}\n{format_search_blocked_until(user_row.search_blocked_until)}"

        await interaction.response.send_message(message, ephemeral=True)

    async def _handle_close(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message("Bot em arranque. Tenta outra vez.", ephemeral=True)
            return
        if interaction.user is None:
            return

        async with self._session_factory() as session:
            try:
                lobby = await lobby_service.get_lobby_detail(session, self.lobby_id)
            except LobbyNotFoundError:
                await interaction.response.send_message("Lobby não encontrado.", ephemeral=True)
                return

        if lobby.host_id != interaction.user.id:
            await interaction.response.send_message(
                "Só o host pode fechar este grupo.", ephemeral=True
            )
            return

        async with self._session_factory() as session:
            async with session.begin():
                try:
                    await lobby_service.close_lobby_as_host(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        host_id=interaction.user.id,
                    )
                except LobbyNotJoinableError as exc:
                    await interaction.response.send_message(str(exc), ephemeral=True)
                    return

        await interaction.response.send_message("Grupo fechado.", ephemeral=True)

    async def _handle_kick_prompt(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message("Bot em arranque. Tenta outra vez.", ephemeral=True)
            return
        if interaction.user is None:
            return

        async with self._session_factory() as session:
            try:
                lobby = await lobby_service.get_lobby_detail(session, self.lobby_id)
            except LobbyNotFoundError:
                await interaction.response.send_message("Lobby não encontrado.", ephemeral=True)
                return

        if lobby.host_id != interaction.user.id:
            await interaction.response.send_message(
                "Só o host pode expulsar jogadores.", ephemeral=True
            )
            return

        members = [
            (m.user.discord_id, m.user.name)
            for m in lobby.members
            if m.left_at is None and m.user.discord_id != lobby.host_id
        ]
        if not members:
            await interaction.response.send_message(
                "Ninguém na lista para expulsar.", ephemeral=True
            )
            return

        view = KickMemberView(
            self.lobby_id, self._session_factory, self._event_bus, members
        )
        await interaction.response.send_message(
            "Escolhe o jogador a expulsar do lobby:",
            view=view,
            ephemeral=True,
        )

    def refresh_buttons(self, lobby_state: str, slots_free: int) -> None:
        active = lobby_state in ("open", "full")
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if not item.custom_id:
                continue
            if item.custom_id.startswith("lfg:join:"):
                item.disabled = not active or slots_free <= 0
            elif item.custom_id.startswith("lfg:leave:"):
                item.disabled = not active
            elif item.custom_id.startswith("lfg:close:"):
                item.disabled = not active
            elif item.custom_id.startswith("lfg:kick:"):
                item.disabled = not active


def register_persistent_views(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    lobby_ids: list[UUID],
) -> None:
    for lobby_id in lobby_ids:
        view = LobbyView(lobby_id)
        view.bind(session_factory, event_bus)
        bot.add_view(view)
