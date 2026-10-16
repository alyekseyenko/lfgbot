from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.host_cooldown import resolve_host_recreate_cooldown
from app.bot.lobby_post import publish_lobby
from app.core.config import Settings
from app.core.events import EventBus
from app.services import lobbies as lobby_service
from app.services.errors import (
    HostRecreateBlockedError,
    PartyCodeInUseError,
    RankRangeError,
    SearchBlockedError,
)
from app.services.guild_config import GuildConfigService
from app.services.lobby_source import LOBBY_SOURCE_UNKNOWN

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LobbyCreateParams:
    mode: str
    slots: int
    party_code: str | None
    min_rank: str | None
    max_rank: str | None
    party_code_public: bool = True
    wanted_agents: list[str] = ()
    ranks_verified: bool = False
    post_style: str = "simple"


def _rank_summary(min_rank: str | None, max_rank: str | None) -> str:
    if min_rank and max_rank:
        return f"{min_rank} – {max_rank}"
    if min_rank:
        return f"mín. {min_rank}"
    if max_rank:
        return f"máx. {max_rank}"
    return "qualquer rank"


async def begin_lobby_create(
    bot: commands.Bot,
    channel: discord.abc.Messageable,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    *,
    host: discord.Member,
    params: LobbyCreateParams,
    interaction: discord.Interaction | None = None,
    reference: discord.Message | None = None,
    guild_config: GuildConfigService | None = None,
    create_source: str = LOBBY_SOURCE_UNKNOWN,
) -> Literal["published", "pending_replace", "rejected"]:
    try:
        from app.services.ranks import validate_rank_range

        validate_rank_range(params.min_rank, params.max_rank)
    except RankRangeError as exc:
        message = str(exc)
        if interaction is not None:
            await interaction.followup.send(message, ephemeral=True)
        return "rejected"

    async with session_factory() as session:
        existing = await lobby_service.get_host_active_lobby(session, host.id)

    if existing is None:
        try:
            await publish_lobby(
                bot,
                channel,
                settings,
                session_factory,
                event_bus,
                host=host,
                mode=params.mode,
                slots=params.slots,
                party_code=params.party_code,
                min_rank=params.min_rank,
                max_rank=params.max_rank,
                party_code_public=params.party_code_public,
                wanted_agents=list(params.wanted_agents),
                ranks_verified=params.ranks_verified,
                post_style=params.post_style,
                reference=reference,
                guild_config=guild_config,
                create_source=create_source,
            )
        except (SearchBlockedError, HostRecreateBlockedError, PartyCodeInUseError) as exc:
            if interaction is not None:
                await interaction.followup.send(str(exc), ephemeral=True)
            return "rejected"
        if interaction is not None:
            await interaction.followup.send("Pedido publicado.", ephemeral=True)
        return "published"

    view = ReplaceLobbyView(
        bot=bot,
        channel=channel,
        settings=settings,
        session_factory=session_factory,
        event_bus=event_bus,
        host_id=host.id,
        previous_lobby_id=existing.id,
        params=params,
        reference=reference,
        guild_config=guild_config,
        create_source=create_source,
    )
    summary = (
        f"Já tens um lobby **{existing.mode}** aberto ({existing.slots} vagas, "
        f"ranks: {_rank_summary(existing.min_rank, existing.max_rank)}).\n"
        "Queres **fechar o anterior** e publicar este novo pedido?"
    )
    if interaction is not None:
        await interaction.followup.send(summary, view=view, ephemeral=True)
    elif isinstance(channel, discord.abc.Messageable):
        await channel.send(
            f"{host.mention} {summary}",
            view=view,
            reference=reference,
            allowed_mentions=discord.AllowedMentions(users=[host.id]),
        )
    return "pending_replace"


class ReplaceLobbyView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: commands.Bot,
        channel: discord.abc.Messageable,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        host_id: int,
        previous_lobby_id: UUID,
        params: LobbyCreateParams,
        reference: discord.Message | None,
        guild_config: GuildConfigService | None = None,
        create_source: str = LOBBY_SOURCE_UNKNOWN,
    ) -> None:
        super().__init__(timeout=120)
        self._create_source = create_source
        self._bot = bot
        self._channel = channel
        self._settings = settings
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._host_id = host_id
        self._previous_lobby_id = previous_lobby_id
        self._params = params
        self._reference = reference
        self._guild_config = guild_config

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None or interaction.user.id != self._host_id:
            await interaction.response.send_message(
                "Só quem criou o pedido pode confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Fechar anterior e criar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        host = interaction.user
        if not isinstance(host, discord.Member):
            await interaction.followup.send("Comando só no servidor.", ephemeral=True)
            return

        try:
            host_recreate_cooldown = await resolve_host_recreate_cooldown(
                self._guild_config,
                self._session_factory,
                host,
                self._channel,
            )
            async with self._session_factory() as session:
                async with session.begin():
                    await lobby_service.close_lobby_as_host(
                        session,
                        self._event_bus,
                        lobby_id=self._previous_lobby_id,
                        host_id=self._host_id,
                        host_recreate_cooldown=host_recreate_cooldown,
                        apply_host_recreate_cooldown_on_close=False,
                    )

            await publish_lobby(
                self._bot,
                self._channel,
                self._settings,
                self._session_factory,
                self._event_bus,
                host=host,
                mode=self._params.mode,
                slots=self._params.slots,
                party_code=self._params.party_code,
                min_rank=self._params.min_rank,
                max_rank=self._params.max_rank,
                party_code_public=self._params.party_code_public,
                wanted_agents=list(self._params.wanted_agents),
                ranks_verified=self._params.ranks_verified,
                reference=self._reference,
                guild_config=self._guild_config,
                create_source=self._create_source,
                post_style=self._params.post_style,
            )
        except (SearchBlockedError, HostRecreateBlockedError, PartyCodeInUseError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("replace lobby failed for host %s", self._host_id)
            await interaction.followup.send(
                "Não foi possível fechar o lobby anterior ou criar o novo. Tenta outra vez.",
                ephemeral=True,
            )
            return

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.followup.send(
            "Lobby anterior fechado. Novo pedido publicado.", ephemeral=True
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            content="Pedido cancelado — o teu lobby anterior mantém-se aberto.",
            view=self,
        )
