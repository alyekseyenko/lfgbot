import asyncio
import logging

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.client import create_bot
from app.bot.embed_updater import EmbedUpdater
from app.bot.gamification_roles import attach_gamification_listener
from app.bot.gamification_tasks import leaderboard_loop
from app.bot.tasks import expiration_loop
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.logging import setup_logging
from app.db.session import create_engine, create_session_factory, verify_database_connection

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

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

    embed_updater = EmbedUpdater(settings, session_factory, event_bus)
    embed_updater.attach()

    bot = create_bot(settings, session_factory, event_bus, embed_updater)
    embed_updater.set_bot(bot)
    attach_gamification_listener(bot, settings, session_factory, event_bus)

    updater_task = asyncio.create_task(embed_updater.run(), name="embed-updater")
    expire_task = asyncio.create_task(
        expiration_loop(settings, session_factory, event_bus, embed_updater),
        name="expiration-loop",
    )
    leaderboard_task = asyncio.create_task(
        leaderboard_loop(bot, settings, session_factory),
        name="leaderboard-loop",
    )

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
        updater_task.cancel()
        expire_task.cancel()
        leaderboard_task.cancel()
        await asyncio.gather(
            updater_task, expire_task, leaderboard_task, return_exceptions=True
        )
        await engine.dispose()
        logger.info("shutdown complete")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
