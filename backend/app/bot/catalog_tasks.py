import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.valorant_catalog import sync_valorant_catalog

logger = logging.getLogger(__name__)


async def valorant_catalog_loop(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    interval = max(3600.0, float(settings.valorant_catalog_sync_hours) * 3600.0)
    while True:
        try:
            async with session_factory() as session:
                async with session.begin():
                    await sync_valorant_catalog(session)
        except Exception:
            logger.exception("valorant catalog sync failed")
        await asyncio.sleep(interval)
