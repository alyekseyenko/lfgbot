from __future__ import annotations

from dataclasses import dataclass

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.events import EventBus
from app.services.guild_config import GuildConfigService


@dataclass
class ApiState:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    bot: discord.Client | None
    guild_config: GuildConfigService
    event_bus: EventBus
