import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embed_updater import EmbedUpdater
from app.core.config import Settings
from app.core.events import EventBus
from app.services.lobbies import expire_due_lobbies

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
                    expired = await expire_due_lobbies(
                        session, event_bus, now=datetime.now(UTC)
                    )
            for lobby in expired:
                await embed_updater.refresh_now(lobby.id)
        except Exception:
            logger.exception("expiration job failed")
        await asyncio.sleep(settings.expire_poll_seconds)
