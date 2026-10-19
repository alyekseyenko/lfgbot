from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.discord_roles import extract_agents_from_member
from app.bot.host_cooldown import resolve_host_recreate_cooldown
from app.bot.lfg_panel import (
    RANK_SELECT_NONE,
    rank_from_select_value,
    rank_select_options_with_default,
)
from app.bot.party_code_config import resolve_party_code_max_length
from app.bot.interaction_obs import track_interaction
from app.bot.members import upsert_user_from_member
from app.core.events import EventBus
from app.db.models import Lobby, User
from app.services import lobbies as lobby_service
from app.services.errors import (
    LobbyEditError,
    LobbyFullError,
    LobbyNotFoundError,
    LobbyNotJoinableError,
    NotInLobbyError,
    PartyCodeInUseError,
    PartyCodeInvalidError,
    RankRangeError,
    SearchBlockedError,
)
from app.services.lobby_patch import LobbyHostPatch
from app.services.party_code import normalize_party_code
from app.services.guild_config import GuildConfigService
from app.services.ranks import validate_rank_range
from app.services.lobby_post_style import is_simple_post_style
from app.services.search_cooldown import SearchCooldownPolicy, format_search_blocked_until

logger = logging.getLogger(__name__)


def join_custom_id(lobby_id: UUID) -> str:
    return f"lfg:join:{lobby_id}"


def leave_custom_id(lobby_id: UUID) -> str:
    return f"lfg:leave:{lobby_id}"


def close_custom_id(lobby_id: UUID) -> str:
    return f"lfg:close:{lobby_id}"


def kick_custom_id(lobby_id: UUID) -> str:
    return f"lfg:kick:{lobby_id}"


def edit_custom_id(lobby_id: UUID) -> str:
    return f"lfg:edit:{lobby_id}"


def _parse_edit_slots(raw: str) -> int | None:
    text = raw.strip()
    if not text.isdigit():
        return None
    slots = int(text)
    if slots < 1 or slots > 4:
        return None
    return slots


class _LobbyEditHostCheck:
    def __init__(self, host_id: int) -> None:
        self._host_id = host_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None or interaction.user.id != self._host_id:
            await interaction.response.send_message(
                "Só quem criou o pedido pode editá-lo.", ephemeral=True
            )
            return False
        return True


class LobbyEditRankView(discord.ui.View):
    """Passo 2 da edição: ranks com selects (igual ao criar pedido simples)."""

    def __init__(
        self,
        owner: SimpleLobbyView | LobbyView,
        *,
        host_id: int,
        slots: int,
        party_code: str | None,
        initial_min: str | None,
        initial_max: str | None,
        party_code_max_length: int,
    ) -> None:
        super().__init__(timeout=180)
        self._owner = owner
        self._slots = slots
        self._party_code = party_code
        self._party_code_max_length = party_code_max_length
        self._min_rank = initial_min
        self._max_rank = initial_max
        self._check = _LobbyEditHostCheck(host_id)

        any_rank_btn = discord.ui.Button(
            label="Qualquer rank (sem limites)",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        any_rank_btn.callback = self._on_any_rank
        self.add_item(any_rank_btn)

        self._min_select = discord.ui.Select(
            placeholder="Rank mínimo (opcional)",
            options=rank_select_options_with_default(initial_min),
            min_values=1,
            max_values=1,
            row=1,
        )
        self._min_select.callback = self._on_min_rank
        self.add_item(self._min_select)

        self._max_select = discord.ui.Select(
            placeholder="Rank máximo (opcional)",
            options=rank_select_options_with_default(initial_max),
            min_values=1,
            max_values=1,
            row=2,
        )
        self._max_select.callback = self._on_max_rank
        self.add_item(self._max_select)

        save_btn = discord.ui.Button(
            label="Guardar alterações",
            style=discord.ButtonStyle.success,
            row=3,
        )
        save_btn.callback = self._on_save
        self.add_item(save_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self._check.interaction_check(interaction)

    async def _on_min_rank(self, interaction: discord.Interaction) -> None:
        chosen = self._min_select.values[0] if self._min_select.values else RANK_SELECT_NONE
        self._min_rank = rank_from_select_value(chosen)
        await interaction.response.defer()

    async def _on_max_rank(self, interaction: discord.Interaction) -> None:
        chosen = self._max_select.values[0] if self._max_select.values else RANK_SELECT_NONE
        self._max_rank = rank_from_select_value(chosen)
        await interaction.response.defer()

    async def _on_any_rank(self, interaction: discord.Interaction) -> None:
        await self._finish_save(interaction, min_rank=None, max_rank=None)

    async def _on_save(self, interaction: discord.Interaction) -> None:
        await self._finish_save(
            interaction, min_rank=self._min_rank, max_rank=self._max_rank
        )

    async def _finish_save(
        self,
        interaction: discord.Interaction,
        *,
        min_rank: str | None,
        max_rank: str | None,
    ) -> None:
        try:
            validate_rank_range(min_rank, max_rank)
        except RankRangeError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        await self._owner.apply_lobby_edit(
            interaction,
            slots=self._slots,
            party_code=self._party_code,
            min_rank=min_rank,
            max_rank=max_rank,
            party_code_max_length=self._party_code_max_length,
            followup=True,
        )


class SimpleEditLobbyModal(discord.ui.Modal, title="Editar pedido"):
    def __init__(
        self,
        owner: SimpleLobbyView | LobbyView,
        lobby: Lobby,
        *,
        code_max_length: int,
    ) -> None:
        super().__init__()
        self._owner = owner
        self._lobby = lobby
        self._code_max_length = code_max_length
        has_code = bool((lobby.party_code or "").strip())
        self.vagas = discord.ui.TextInput(
            label="Quantas vagas? (1 a 4)",
            default=str(lobby.slots),
            min_length=1,
            max_length=1,
            required=True,
        )
        self.codigo = discord.ui.TextInput(
            label=f"Código da party ({code_max_length} caracteres)",
            default=(lobby.party_code or "")[:code_max_length],
            min_length=code_max_length if has_code else 0,
            max_length=code_max_length,
            required=has_code,
        )
        self.add_item(self.vagas)
        self.add_item(self.codigo)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        slots = _parse_edit_slots(str(self.vagas.value))
        if slots is None:
            await interaction.response.send_message(
                "Vagas inválidas — escolhe um número de **1** a **4**.",
                ephemeral=True,
            )
            return
        code_raw = str(self.codigo.value).strip()
        party_code: str | None
        if code_raw:
            try:
                party_code = normalize_party_code(
                    code_raw, max_length=self._code_max_length
                )
            except PartyCodeInvalidError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
        else:
            party_code = None
        if interaction.user is None:
            return
        await interaction.response.send_message(
            "Ajusta os **ranks** como ao criar o pedido. "
            "**Qualquer rank** remove limites; ou escolhe mín./máx. e **Guardar alterações**.",
            view=LobbyEditRankView(
                self._owner,
                host_id=interaction.user.id,
                slots=slots,
                party_code=party_code,
                initial_min=self._lobby.min_rank,
                initial_max=self._lobby.max_rank,
                party_code_max_length=self._code_max_length,
            ),
            ephemeral=True,
        )


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
        return f"Entraste no lobby.\n**Código da party:**\n```{party_code}```"
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
            await interaction.followup.send("Não foi possível expulsar o jogador.", ephemeral=True)
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


class SimpleLobbyView(discord.ui.View):
    """Pedido simples: o host fecha/edita com botões (opcionais) ou /fechar e /editar."""

    def __init__(
        self,
        lobby_id: UUID,
        *,
        show_close_button: bool = True,
        show_edit_button: bool = True,
    ) -> None:
        super().__init__(timeout=None)
        self.lobby_id = lobby_id
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._event_bus: EventBus | None = None
        self._guild_config: GuildConfigService | None = None
        if show_edit_button:
            edit_btn = discord.ui.Button(
                label="Editar",
                style=discord.ButtonStyle.secondary,
                custom_id=edit_custom_id(lobby_id),
                row=0,
            )
            edit_btn.callback = self._edit_callback
            self.add_item(edit_btn)
        if show_close_button:
            close_btn = discord.ui.Button(
                label="Fechar",
                style=discord.ButtonStyle.danger,
                custom_id=close_custom_id(lobby_id),
                row=0,
            )
            close_btn.callback = self._close_callback
            self.add_item(close_btn)

    def bind(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        guild_config: GuildConfigService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._guild_config = guild_config

    async def _close_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_close(interaction)

    async def _edit_callback(self, interaction: discord.Interaction) -> None:
        await self._handle_edit(interaction)

    async def _handle_close(self, interaction: discord.Interaction) -> None:
        helper = LobbyView(self.lobby_id)
        helper.bind(self._session_factory, self._event_bus, self._guild_config)
        await helper._handle_close(interaction)

    async def _handle_edit(self, interaction: discord.Interaction) -> None:
        helper = LobbyView(self.lobby_id)
        helper.bind(self._session_factory, self._event_bus, self._guild_config)
        await helper._handle_edit(interaction)

    async def apply_lobby_edit(
        self,
        interaction: discord.Interaction,
        *,
        slots: int,
        party_code: str | None,
        min_rank: str | None,
        max_rank: str | None,
        party_code_max_length: int,
        followup: bool = False,
    ) -> None:
        helper = LobbyView(self.lobby_id)
        helper.bind(self._session_factory, self._event_bus, self._guild_config)
        await helper.apply_lobby_edit(
            interaction,
            slots=slots,
            party_code=party_code,
            min_rank=min_rank,
            max_rank=max_rank,
            party_code_max_length=party_code_max_length,
            followup=followup,
        )

    def refresh_buttons(self, lobby_state: str, _slots_free: int) -> None:
        active = lobby_state in ("open", "full")
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if item.custom_id and (
                item.custom_id.startswith("lfg:close:")
                or item.custom_id.startswith("lfg:edit:")
            ):
                item.disabled = not active


def make_lobby_view(
    lobby_id: UUID,
    post_style: str | None,
    *,
    show_close_button: bool = True,
    show_edit_button: bool = True,
) -> LobbyView | SimpleLobbyView:
    if is_simple_post_style(post_style):
        return SimpleLobbyView(
            lobby_id,
            show_close_button=show_close_button,
            show_edit_button=show_edit_button,
        )
    return LobbyView(lobby_id, show_edit_button=show_edit_button)


class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: UUID, *, show_edit_button: bool = True) -> None:
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
        if show_edit_button:
            edit_btn = discord.ui.Button(
                label="Editar",
                style=discord.ButtonStyle.secondary,
                custom_id=edit_custom_id(lobby_id),
                row=0,
            )
            edit_btn.callback = self._edit_callback
            self.add_item(edit_btn)
        self.add_item(close_btn)
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._event_bus: EventBus | None = None
        self._guild_config: GuildConfigService | None = None

    def bind(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        guild_config: GuildConfigService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._guild_config = guild_config

    async def _join_callback(self, interaction: discord.Interaction) -> None:
        async with track_interaction(interaction, lobby_id=str(self.lobby_id)):
            await self._handle_join(interaction)

    async def _leave_callback(self, interaction: discord.Interaction) -> None:
        async with track_interaction(interaction, lobby_id=str(self.lobby_id)):
            await self._handle_leave(interaction)

    async def _close_callback(self, interaction: discord.Interaction) -> None:
        async with track_interaction(interaction, lobby_id=str(self.lobby_id)):
            await self._handle_close(interaction)

    async def _kick_callback(self, interaction: discord.Interaction) -> None:
        async with track_interaction(interaction, lobby_id=str(self.lobby_id)):
            await self._handle_kick_prompt(interaction)

    async def _edit_callback(self, interaction: discord.Interaction) -> None:
        async with track_interaction(interaction, lobby_id=str(self.lobby_id)):
            await self._handle_edit(interaction)

    async def _handle_join(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.", ephemeral=True
            )
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
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.", ephemeral=True
            )
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
                    policy: SearchCooldownPolicy | None = None
                    if self._guild_config is not None and interaction.guild is not None:
                        cfg = await self._guild_config.get_config(session, interaction.guild.id)
                        policy = cfg.search_cooldown_policy()
                    await lobby_service.leave_lobby(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        user=user,
                        reason="left",
                        search_cooldown_policy=policy,
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
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.", ephemeral=True
            )
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

        channel = interaction.channel
        host = interaction.user
        if channel is None or not isinstance(host, discord.Member):
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        host_recreate_cooldown = await resolve_host_recreate_cooldown(
            self._guild_config,
            self._session_factory,
            host,
            channel,
        )
        cooldown_secs = int(host_recreate_cooldown.total_seconds())

        async with self._session_factory() as session:
            async with session.begin():
                try:
                    await lobby_service.close_lobby_as_host(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        host_id=interaction.user.id,
                        host_recreate_cooldown=host_recreate_cooldown,
                    )
                except LobbyNotJoinableError as exc:
                    await interaction.response.send_message(str(exc), ephemeral=True)
                    return

        if cooldown_secs <= 0:
            close_note = "Grupo fechado. Podes criar outro pedido já."
        else:
            close_note = (
                f"Grupo fechado. Podes criar outro pedido em **{cooldown_secs}** s "
                f"(tempo definido pelas tuas roles ao fechar)."
            )
        await interaction.response.send_message(close_note, ephemeral=True)

    async def _handle_edit(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.", ephemeral=True
            )
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
                "Só quem criou o pedido pode editá-lo.", ephemeral=True
            )
            return
        if lobby.state.value not in ("open", "full"):
            await interaction.response.send_message(
                "Este pedido já não está ativo.", ephemeral=True
            )
            return
        code_len = await resolve_party_code_max_length(
            self._guild_config,
            self._session_factory,
            interaction.guild.id if interaction.guild else None,
        )
        await interaction.response.send_modal(
            SimpleEditLobbyModal(self, lobby, code_max_length=code_len)
        )

    async def apply_lobby_edit(
        self,
        interaction: discord.Interaction,
        *,
        slots: int,
        party_code: str | None,
        min_rank: str | None,
        max_rank: str | None,
        party_code_max_length: int,
        followup: bool = False,
    ) -> None:
        if self._session_factory is None or self._event_bus is None:
            msg = "Bot em arranque. Tenta outra vez."
            if followup:
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        if interaction.user is None:
            return
        patch = LobbyHostPatch(
            slots=slots,
            party_code=party_code,
            min_rank=min_rank,
            max_rank=max_rank,
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await lobby_service.update_lobby_as_host(
                        session,
                        self._event_bus,
                        lobby_id=self.lobby_id,
                        host_id=interaction.user.id,
                        patch=patch,
                        party_code_max_length=party_code_max_length,
                    )
        except (
            LobbyEditError,
            LobbyNotJoinableError,
            RankRangeError,
            PartyCodeInUseError,
            PartyCodeInvalidError,
        ) as exc:
            if followup:
                await interaction.followup.send(str(exc), ephemeral=True)
            else:
                await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("edit failed in lobby %s", self.lobby_id)
            err = "Não foi possível editar o pedido. Tenta outra vez."
            if followup:
                await interaction.followup.send(err, ephemeral=True)
            else:
                await interaction.response.send_message(err, ephemeral=True)
            return
        ok = "Pedido atualizado. A mensagem no canal foi refrescada."
        if followup:
            await interaction.followup.send(ok, ephemeral=True)
        else:
            await interaction.response.send_message(ok, ephemeral=True)

    async def _handle_kick_prompt(self, interaction: discord.Interaction) -> None:
        if self._session_factory is None or self._event_bus is None:
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.", ephemeral=True
            )
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

        view = KickMemberView(self.lobby_id, self._session_factory, self._event_bus, members)
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
            elif item.custom_id.startswith("lfg:edit:"):
                item.disabled = not active


def register_persistent_views(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    lobbies: list[Lobby],
    guild_config: GuildConfigService | None = None,
) -> None:
    for lobby in lobbies:
        view = make_lobby_view(lobby.id, lobby.post_style)
        view.bind(session_factory, event_bus, guild_config)
        bot.add_view(view)
