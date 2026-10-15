import logging
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.cog_lfg import setup_lfg_cog
from app.bot.embed_updater import EmbedUpdater
from app.bot.lfg_panel import ensure_lfg_panels, register_create_panel_view
from app.bot.views import LobbyView, register_persistent_views
from app.core.config import Settings
from app.core.events import EventBus
from app.services import lobbies as lobby_service

logger = logging.getLogger(__name__)


def create_bot(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    embed_updater: EmbedUpdater,
) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = settings.auto_format_messages

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        logger.info("discord bot logged in as %s (%s)", bot.user, bot.user and bot.user.id)
        if getattr(bot, "_lfg_panels_ensured", False):
            return
        bot._lfg_panels_ensured = True
        try:
            await ensure_lfg_panels(bot, settings, session_factory, event_bus)
        except Exception:
            logger.exception("falha ao garantir painéis LFG — usa /lfg-painel manualmente")

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger.exception("slash command error: %s", error)
        message = "Ocorreu um erro. Tenta outra vez."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @bot.event
    async def setup_hook() -> None:
        try:
            await _reconcile_on_startup(bot, settings, session_factory, event_bus, embed_updater)
        except Exception:
            logger.exception("startup reconcile failed — bot continua, mas verifica a BD")
        await setup_lfg_cog(bot, settings, session_factory, event_bus)

        guild_ids = settings.discord_guild_id_list
        tree_cmds = [cmd.name for cmd in bot.tree.walk_commands()]
        logger.info("commands in tree before sync: %s", tree_cmds)

        if guild_ids:
            for guild_id in guild_ids:
                guild = discord.Object(id=guild_id)
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                names = [cmd.name for cmd in synced]
                logger.info(
                    "synced %s slash commands to guild %s: %s",
                    len(synced),
                    guild_id,
                    names,
                )
        else:
            synced = await bot.tree.sync()
            names = [cmd.name for cmd in synced]
            logger.info("synced %s global slash commands: %s", len(synced), names)

    return bot


async def _reconcile_on_startup(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    embed_updater: EmbedUpdater,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            expired = await lobby_service.expire_due_lobbies(
                session, event_bus, now=datetime.now(UTC)
            )
            active = await lobby_service.list_active_lobbies(session)

    for lobby in expired:
        await embed_updater.refresh_now(lobby.id)

    register_persistent_views(
        bot, session_factory, event_bus, [lobby.id for lobby in active]
    )
    register_create_panel_view(bot, settings, session_factory, event_bus)

    for lobby in active:
        await embed_updater.refresh_now(lobby.id)

    logger.info("reconciled %s active lobbies on startup", len(active))
