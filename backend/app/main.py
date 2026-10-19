import asyncio
import logging

import discord
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import create_api_app
from app.bot.client import create_bot
from app.bot.embed_updater import EmbedUpdater
from app.bot.creator_level_roles import attach_creator_level_listener
from app.bot.creator_level_tasks import creator_weekly_leaderboard_loop
from app.bot.reputation_reactions import attach_reputation_reaction_handlers
from app.bot.reputation_tasks import reputation_request_loop, reputation_weekly_loop
from app.bot.gamification_roles import attach_gamification_listener
from app.bot.gamification_tasks import leaderboard_loop
from app.bot.guild_audit_log import attach_guild_audit_listener
from app.bot.catalog_tasks import valorant_catalog_loop
from app.bot.tasks import embed_reconciliation_loop, expiration_loop
from app.core.config import get_settings
from app.core.domain_event_session import set_domain_event_bus
from app.core.events import EventBus
from app.core.logging import setup_logging
from app.db.session import create_engine, create_session_factory, verify_database_connection
from app.services.guild_config import GuildConfigService

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, json_logs=settings.log_json)
    if settings.sentry_dsn.strip():
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn.strip(), traces_sample_rate=0.0)
        except Exception:
            logger.exception("failed to init sentry")

    if not settings.discord_token:
        raise SystemExit("DISCORD_TOKEN is required")

    engine = create_engine(settings)
    try:
        await verify_database_connection(engine)
    except Exception:
        logger.exception("failed to connect to database")
        raise

    session_factory: async_sessionmaker[AsyncSession] = create_session_factory(engine)
    event_bus = EventBus()
    set_domain_event_bus(event_bus)
    guild_config = GuildConfigService(settings)

    embed_updater = EmbedUpdater(settings, session_factory, event_bus, guild_config)
    embed_updater.attach()

    bot = create_bot(settings, session_factory, event_bus, embed_updater, guild_config)
    embed_updater.set_bot(bot)
    attach_gamification_listener(bot, settings, session_factory, event_bus)
    attach_creator_level_listener(bot, session_factory, event_bus, guild_config)
    attach_reputation_reaction_handlers(bot, session_factory, guild_config)
    attach_guild_audit_listener(bot, session_factory, event_bus, guild_config)

    api_app = create_api_app(settings, session_factory, bot, guild_config, event_bus)
    api_config = uvicorn.Config(
        api_app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    api_server = uvicorn.Server(api_config)

    updater_task = asyncio.create_task(embed_updater.run(), name="embed-updater")
    expire_task = asyncio.create_task(
        expiration_loop(settings, session_factory, event_bus, embed_updater),
        name="expiration-loop",
    )
    reconcile_task = asyncio.create_task(
        embed_reconciliation_loop(settings, session_factory, embed_updater),
        name="embed-reconciliation-loop",
    )
    leaderboard_task = asyncio.create_task(
        leaderboard_loop(bot, settings, session_factory, guild_config),
        name="leaderboard-loop",
    )
    creator_weekly_task = asyncio.create_task(
        creator_weekly_leaderboard_loop(bot, settings, session_factory, guild_config),
        name="creator-weekly-leaderboard-loop",
    )
    reputation_request_task = asyncio.create_task(
        reputation_request_loop(bot, settings, session_factory, guild_config),
        name="reputation-request-loop",
    )
    reputation_weekly_task = asyncio.create_task(
        reputation_weekly_loop(bot, session_factory, guild_config),
        name="reputation-weekly-loop",
    )
    catalog_task = asyncio.create_task(
        valorant_catalog_loop(settings, session_factory),
        name="valorant-catalog-loop",
    )
    api_task = asyncio.create_task(api_server.serve(), name="api-server")

    logger.info("ready")

    try:
        async with bot:
            await bot.start(settings.discord_token)
    except discord.PrivilegedIntentsRequired:
        logger.error(
            "O bot pede intents privilegiados (ex.: Message Content com "
            "AUTO_FORMAT_MESSAGES=true). Ativa no Developer Portal ou põe "
            "AUTO_FORMAT_MESSAGES=false no .env."
        )
        raise SystemExit(1) from None
    finally:
        await embed_updater.shutdown()
        api_server.should_exit = True
        updater_task.cancel()
        expire_task.cancel()
        reconcile_task.cancel()
        leaderboard_task.cancel()
        creator_weekly_task.cancel()
        reputation_request_task.cancel()
        reputation_weekly_task.cancel()
        catalog_task.cancel()
        api_task.cancel()
        await asyncio.gather(
            updater_task,
            expire_task,
            reconcile_task,
            leaderboard_task,
            creator_weekly_task,
            reputation_request_task,
            reputation_weekly_task,
            catalog_task,
            api_task,
            return_exceptions=True,
        )
        await engine.dispose()
        logger.info("shutdown complete")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
