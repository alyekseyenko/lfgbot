import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embed_updater import EmbedUpdater
from app.core.config import Settings
from app.core.events import EventBus
from app.core.metrics import embed_reconcile_lobbies_total, embed_reconcile_runs_total
from app.services.lobbies import expire_due_lobbies
from app.services.lobby_reconcile import reconcile_active_lobby_embeds

logger = logging.getLogger(__name__)


async def expiration_loop(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    embed_updater: EmbedUpdater,
) -> None:
    while True:
        try:
            async with session_factory() as session:
                async with session.begin():
                    expired = await expire_due_lobbies(session, event_bus, now=datetime.now(UTC))
            for lobby in expired:
                await embed_updater.refresh_now(lobby.id)
        except Exception:
            logger.exception("expiration job failed")
        await asyncio.sleep(settings.expire_poll_seconds)


async def embed_reconciliation_loop(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embed_updater: EmbedUpdater,
) -> None:
    while True:
        try:
            if embed_updater.bot_ready():
                count = await reconcile_active_lobby_embeds(
                    session_factory,
                    refresh=embed_updater.refresh_now,
                )
                embed_reconcile_runs_total.inc()
                if count:
                    embed_reconcile_lobbies_total.inc(count)
                    logger.info("embed reconciliation refreshed %s lobbies", count)
        except Exception:
            logger.exception("embed reconciliation job failed")
        await asyncio.sleep(settings.reconcile_poll_seconds)
