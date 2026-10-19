"""Comandos de contexto (clique direito na mensagem → Apps) para canais LFG read-only."""
from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.host_cooldown import resolve_host_recreate_cooldown
from app.bot.lfg_panel import CreateGroupPanelView
from app.bot.party_code_config import resolve_party_code_max_length
from app.bot.views import SimpleLobbyView
from app.core.config import Settings
from app.core.events import EventBus
from app.db.models import Lobby
from app.services import lobbies as lobby_service
from app.services.errors import LobbyNotFoundError, LobbyNotJoinableError
from app.services.guild_config import GuildConfigService

logger = logging.getLogger(__name__)

COG_NAME = "LfgCog"


def _lfg_cog(interaction: discord.Interaction) -> commands.Cog | None:
    if not isinstance(interaction.client, commands.Bot):
        return None
    cog = interaction.client.get_cog(COG_NAME)
    return cog


async def _respond_cog_unavailable(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "Bot em arranque. Tenta outra vez em instantes.",
        ephemeral=True,
    )


@app_commands.context_menu(name="Criar pedido LFG")
async def ctx_criar_pedido(interaction: discord.Interaction, message: discord.Message) -> None:
    cog = _lfg_cog(interaction)
    if cog is None:
        await _respond_cog_unavailable(interaction)
        return
    await handle_context_criar_pedido(
        interaction,
        message,
        bot=cog.bot,
        settings=cog.settings,
        session_factory=cog.session_factory,
        event_bus=cog.event_bus,
        guild_config=cog.guild_config,
    )


@app_commands.context_menu(name="Fechar pedido")
async def ctx_fechar_pedido(interaction: discord.Interaction, message: discord.Message) -> None:
    cog = _lfg_cog(interaction)
    if cog is None:
        await _respond_cog_unavailable(interaction)
        return
    await handle_context_fechar_pedido(
        interaction,
        message,
        bot=cog.bot,
        session_factory=cog.session_factory,
        event_bus=cog.event_bus,
        guild_config=cog.guild_config,
    )


@app_commands.context_menu(name="Editar pedido")
async def ctx_editar_pedido(interaction: discord.Interaction, message: discord.Message) -> None:
    cog = _lfg_cog(interaction)
    if cog is None:
        await _respond_cog_unavailable(interaction)
        return
    await handle_context_editar_pedido(
        interaction,
        message,
        bot=cog.bot,
        session_factory=cog.session_factory,
        event_bus=cog.event_bus,
        guild_config=cog.guild_config,
    )


def register_message_context_menus(bot: commands.Bot) -> None:
    for menu in (ctx_criar_pedido, ctx_fechar_pedido, ctx_editar_pedido):
        if menu.name not in {c.name for c in bot.tree.get_commands()}:
            bot.tree.add_command(menu)


async def _require_lfg_channel(
    interaction: discord.Interaction,
    *,
    guild_config: GuildConfigService,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    if interaction.guild is None or interaction.channel_id is None:
        await interaction.response.send_message("Só no servidor.", ephemeral=True)
        return False
    allowed = await guild_config.channel_allowed(
        session_factory, interaction.guild.id, interaction.channel_id
    )
    if not allowed:
        await interaction.response.send_message(
            "Estas opções só estão disponíveis nos **canais LFG** configurados no admin.",
            ephemeral=True,
        )
        return False
    return True


async def handle_context_criar_pedido(
    interaction: discord.Interaction,
    message: discord.Message,
    *,
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    if not await _require_lfg_channel(
        interaction, guild_config=guild_config, session_factory=session_factory
    ):
        return
    panel = CreateGroupPanelView()
    panel.bind(bot, settings, session_factory, event_bus, guild_config)
    try:
        await panel._on_create(interaction)
    except Exception:
        logger.exception(
            "context criar pedido failed for user %s", interaction.user and interaction.user.id
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Não foi possível abrir o criador de pedido. Tenta outra vez.",
                ephemeral=True,
            )


async def _lobby_from_bot_message(
    interaction: discord.Interaction,
    message: discord.Message,
    *,
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> Lobby | None:
    if message.author is None or message.author.id != bot.user.id:
        await interaction.response.send_message(
            "Usa **Fechar** ou **Editar** na mensagem do **pedido LFG** (embed deste bot).",
            ephemeral=True,
        )
        return None
    if message.channel is None:
        await interaction.response.send_message("Canal inválido.", ephemeral=True)
        return None
    async with session_factory() as session:
        lobby = await lobby_service.get_active_lobby_by_message(
            session,
            channel_id=message.channel.id,
            message_id=message.id,
        )
    if lobby is None:
        await interaction.response.send_message(
            "Esta mensagem não é um pedido LFG ativo.",
            ephemeral=True,
        )
        return None
    return lobby


async def handle_context_fechar_pedido(
    interaction: discord.Interaction,
    message: discord.Message,
    *,
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    if not await _require_lfg_channel(
        interaction, guild_config=guild_config, session_factory=session_factory
    ):
        return
    lobby = await _lobby_from_bot_message(
        interaction, message, bot=bot, session_factory=session_factory
    )
    if lobby is None:
        return
    if interaction.user is None or lobby.host_id != interaction.user.id:
        await interaction.response.send_message(
            "Só quem criou o pedido pode fechá-lo.",
            ephemeral=True,
        )
        return
    channel = interaction.channel
    host = interaction.user
    if channel is None or not isinstance(host, discord.Member):
        await interaction.response.send_message("Canal inválido.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    host_recreate_cooldown = await resolve_host_recreate_cooldown(
        guild_config,
        session_factory,
        host,
        channel,
    )
    try:
        async with session_factory() as session:
            async with session.begin():
                await lobby_service.close_lobby_as_host(
                    session,
                    event_bus,
                    lobby_id=lobby.id,
                    host_id=interaction.user.id,
                    host_recreate_cooldown=host_recreate_cooldown,
                )
    except LobbyNotJoinableError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception:
        logger.exception("context fechar failed for user %s", interaction.user.id)
        await interaction.followup.send(
            "Não foi possível fechar o pedido. Tenta outra vez.",
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        "Grupo fechado. O pedido no canal foi atualizado.",
        ephemeral=True,
    )


async def handle_context_editar_pedido(
    interaction: discord.Interaction,
    message: discord.Message,
    *,
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    if not await _require_lfg_channel(
        interaction, guild_config=guild_config, session_factory=session_factory
    ):
        return
    lobby = await _lobby_from_bot_message(
        interaction, message, bot=bot, session_factory=session_factory
    )
    if lobby is None:
        return
    if interaction.user is None or lobby.host_id != interaction.user.id:
        await interaction.response.send_message(
            "Só quem criou o pedido pode editá-lo.",
            ephemeral=True,
        )
        return
    try:
        async with session_factory() as session:
            await lobby_service.get_lobby_detail(session, lobby.id)
    except LobbyNotFoundError:
        await interaction.response.send_message("Pedido não encontrado.", ephemeral=True)
        return
    view = SimpleLobbyView(lobby.id)
    view.bind(session_factory, event_bus, guild_config)
    await view._handle_edit(interaction)
