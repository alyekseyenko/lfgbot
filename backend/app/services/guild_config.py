from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Guild, GuildRoleMapping, GuildSettings
from app.services.host_recreate_cooldown import (
    DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS,
    DEFAULT_IMMUNE_HOST_RECREATE_COOLDOWN_SECONDS,
    clamp_host_recreate_seconds,
)
from app.services.lfg_embed_style import (
    DEFAULT_COMPETITIVE_COLOR,
    DEFAULT_FOOTER_BRAND,
    DEFAULT_FULL_COLOR,
    DEFAULT_IMMUNE_EMBED_COLOR,
    DEFAULT_IMMUNE_EMBED_LABEL,
    DEFAULT_INACTIVE_COLOR,
    DEFAULT_UNRATED_COLOR,
    LFG_EMBED_COLOR_SOURCES,
    ImmuneEmbedTier,
    immune_embed_tiers_for_config,
    member_has_immune_role,
    normalize_lfg_embed_custom_texts,
    normalize_rank_embed_colors,
    parse_embed_hex_color,
    union_immune_role_ids_from_tiers,
)
from app.services.search_cooldown import (
    DEFAULT_EARLY_MAX_COUNT,
    DEFAULT_EARLY_MINUTES,
    DEFAULT_MID_MINUTES,
    DEFAULT_SEVERE_HOURS,
    SearchCooldownPolicy,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 45.0
MAPPING_TYPES = frozenset({"valorant_rank", "agent_role"})


@dataclass(frozen=True)
class GuildRuntimeConfig:
    discord_guild_id: int
    lfg_channel_ids: tuple[int, ...]
    announce_channel_id: int | None
    auto_format_messages: bool
    default_lfg_mode: str
    gamification_enabled: bool
    stats_channel_id: int
    log_channel_id: int
    panel_sticky_enabled: bool
    lobby_ttl_minutes: int
    immune_role_ids: tuple[int, ...]
    lfg_embed_color_source: str
    rank_embed_colors: dict[str, str]
    lfg_embed_competitive_color: str
    lfg_embed_unrated_color: str
    lfg_embed_full_color: str
    lfg_embed_inactive_color: str
    lfg_embed_decorative: bool
    lfg_embed_footer_brand: str
    lfg_embed_banner_url: str | None
    lfg_embed_custom_texts: dict[str, str]
    lfg_embed_show_author: bool
    lfg_embed_show_timestamp: bool
    lfg_embed_show_thumbnail: bool
    lfg_embed_banner_on_panel: bool
    lfg_embed_banner_on_lobby: bool
    lfg_panel_thumbnail_url: str | None
    lfg_panel_color: str
    lfg_panel_footer_brand: str | None
    lfg_panel_banner_url: str | None
    lfg_panel_decorative: bool
    lfg_embed_thumbnail_url: str | None
    immune_embed_enabled: bool
    immune_embed_color: str
    immune_embed_label: str
    immune_embed_tiers: tuple[ImmuneEmbedTier, ...]
    search_penalty_enabled: bool
    search_penalty_early_minutes: int
    search_penalty_early_max_count: int
    search_penalty_mid_minutes: int
    search_penalty_severe_hours: int
    host_recreate_cooldown_seconds: int
    immune_host_recreate_cooldown_seconds: int
    role_mappings: dict[tuple[str, str], int]

    def host_recreate_cooldown_for_member(self, member: Any | None) -> timedelta:
        if member_has_immune_role(member, self.immune_role_ids):
            seconds = self.immune_host_recreate_cooldown_seconds
        else:
            seconds = self.host_recreate_cooldown_seconds
        return timedelta(seconds=clamp_host_recreate_seconds(seconds))

    def search_cooldown_policy(self) -> SearchCooldownPolicy:
        return SearchCooldownPolicy(
            enabled=self.search_penalty_enabled,
            early_minutes=self.search_penalty_early_minutes,
            early_max_daily_count=self.search_penalty_early_max_count,
            mid_minutes=self.search_penalty_mid_minutes,
            severe_hours=self.search_penalty_severe_hours,
        )

    def channel_allowed(self, channel_id: int, env_fallback: list[int]) -> bool:
        if self.lfg_channel_ids:
            return channel_id in self.lfg_channel_ids
        if env_fallback:
            return channel_id in env_fallback
        return True

    def stats_post_channel_ids(self) -> list[int]:
        if self.stats_channel_id:
            return [self.stats_channel_id]
        return list(self.lfg_channel_ids)

    def ranking_channel_allowed(self, channel_id: int, env_fallback: list[int]) -> bool:
        if self.channel_allowed(channel_id, env_fallback):
            return True
        return bool(self.stats_channel_id) and channel_id == self.stats_channel_id


def _int_list(raw: Any) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _settings_row_to_config(
    guild_id: int,
    row: GuildSettings | None,
    mappings: list[GuildRoleMapping],
    settings: Settings,
) -> GuildRuntimeConfig:
    env_lfg = settings.lfg_channel_id_list if guild_id in settings.discord_guild_id_list else []
    if row is None:
        return GuildRuntimeConfig(
            discord_guild_id=guild_id,
            lfg_channel_ids=tuple(env_lfg),
            announce_channel_id=None,
            auto_format_messages=settings.auto_format_messages,
            default_lfg_mode=settings.default_lfg_mode,
            gamification_enabled=settings.gamification_enabled,
            stats_channel_id=settings.stats_channel_id,
            log_channel_id=0,
            panel_sticky_enabled=settings.panel_sticky_enabled,
            lobby_ttl_minutes=settings.lobby_ttl_minutes,
            immune_role_ids=(),
            lfg_embed_color_source="mode",
            rank_embed_colors={},
            lfg_embed_competitive_color=DEFAULT_COMPETITIVE_COLOR,
            lfg_embed_unrated_color=DEFAULT_UNRATED_COLOR,
            lfg_embed_full_color=DEFAULT_FULL_COLOR,
            lfg_embed_inactive_color=DEFAULT_INACTIVE_COLOR,
            lfg_embed_decorative=True,
            lfg_embed_footer_brand=DEFAULT_FOOTER_BRAND,
            lfg_embed_banner_url=None,
            lfg_embed_custom_texts={},
            lfg_embed_show_author=True,
            lfg_embed_show_timestamp=True,
            lfg_embed_show_thumbnail=True,
            lfg_embed_banner_on_panel=True,
            lfg_embed_banner_on_lobby=True,
            lfg_panel_thumbnail_url=None,
            lfg_panel_color=DEFAULT_COMPETITIVE_COLOR,
            lfg_panel_footer_brand=None,
            lfg_panel_banner_url=None,
            lfg_panel_decorative=True,
            lfg_embed_thumbnail_url=None,
            immune_embed_enabled=True,
            immune_embed_color=DEFAULT_IMMUNE_EMBED_COLOR,
            immune_embed_label=DEFAULT_IMMUNE_EMBED_LABEL,
            immune_embed_tiers=(),
            search_penalty_enabled=True,
            search_penalty_early_minutes=DEFAULT_EARLY_MINUTES,
            search_penalty_early_max_count=DEFAULT_EARLY_MAX_COUNT,
            search_penalty_mid_minutes=DEFAULT_MID_MINUTES,
            search_penalty_severe_hours=DEFAULT_SEVERE_HOURS,
            host_recreate_cooldown_seconds=DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS,
            immune_host_recreate_cooldown_seconds=DEFAULT_IMMUNE_HOST_RECREATE_COOLDOWN_SECONDS,
            role_mappings={},
        )
    lfg_ids = _int_list(row.lfg_channel_ids)
    if not lfg_ids and env_lfg:
        lfg_ids = env_lfg
    mapping_dict = {(m.mapping_type, m.logical_key): int(m.discord_role_id) for m in mappings}
    legacy_immune_ids = tuple(_int_list(row.immune_role_ids))
    embed_tiers = immune_embed_tiers_for_config(
        row.immune_embed_tiers,
        legacy_role_ids=legacy_immune_ids,
        legacy_label=(row.immune_embed_label or DEFAULT_IMMUNE_EMBED_LABEL),
        legacy_color=row.immune_embed_color or DEFAULT_IMMUNE_EMBED_COLOR,
    )
    tier_ids = union_immune_role_ids_from_tiers(embed_tiers)
    immune_ids = tuple(sorted(set(tier_ids) | set(legacy_immune_ids)))
    return GuildRuntimeConfig(
        discord_guild_id=guild_id,
        lfg_channel_ids=tuple(lfg_ids),
        announce_channel_id=row.announce_channel_id,
        auto_format_messages=row.auto_format_messages,
        default_lfg_mode=row.default_lfg_mode,
        gamification_enabled=row.gamification_enabled,
        stats_channel_id=int(row.stats_channel_id or 0),
        log_channel_id=int(row.log_channel_id or 0),
        panel_sticky_enabled=row.panel_sticky_enabled,
        lobby_ttl_minutes=row.lobby_ttl_minutes,
        immune_role_ids=immune_ids,
        lfg_embed_color_source=(
            row.lfg_embed_color_source
            if row.lfg_embed_color_source in LFG_EMBED_COLOR_SOURCES
            else "mode"
        ),
        rank_embed_colors=normalize_rank_embed_colors(row.rank_embed_colors),
        lfg_embed_competitive_color=parse_embed_hex_color(
            row.lfg_embed_competitive_color, default=DEFAULT_COMPETITIVE_COLOR
        ),
        lfg_embed_unrated_color=parse_embed_hex_color(
            row.lfg_embed_unrated_color, default=DEFAULT_UNRATED_COLOR
        ),
        lfg_embed_full_color=parse_embed_hex_color(
            row.lfg_embed_full_color, default=DEFAULT_FULL_COLOR
        ),
        lfg_embed_inactive_color=parse_embed_hex_color(
            row.lfg_embed_inactive_color, default=DEFAULT_INACTIVE_COLOR
        ),
        lfg_embed_decorative=bool(row.lfg_embed_decorative),
        lfg_embed_footer_brand=(
            (row.lfg_embed_footer_brand or DEFAULT_FOOTER_BRAND).strip()[:64] or DEFAULT_FOOTER_BRAND
        ),
        lfg_embed_banner_url=(row.lfg_embed_banner_url or "").strip() or None,
        lfg_embed_custom_texts=normalize_lfg_embed_custom_texts(row.lfg_embed_custom_texts),
        lfg_embed_show_author=bool(row.lfg_embed_show_author),
        lfg_embed_show_timestamp=bool(row.lfg_embed_show_timestamp),
        lfg_embed_show_thumbnail=bool(row.lfg_embed_show_thumbnail),
        lfg_embed_banner_on_panel=bool(row.lfg_embed_banner_on_panel),
        lfg_embed_banner_on_lobby=bool(row.lfg_embed_banner_on_lobby),
        lfg_panel_thumbnail_url=(row.lfg_panel_thumbnail_url or "").strip() or None,
        lfg_panel_color=parse_embed_hex_color(row.lfg_panel_color, default=DEFAULT_COMPETITIVE_COLOR),
        lfg_panel_footer_brand=(row.lfg_panel_footer_brand or "").strip()[:64] or None,
        lfg_panel_banner_url=(row.lfg_panel_banner_url or "").strip() or None,
        lfg_panel_decorative=bool(row.lfg_panel_decorative),
        lfg_embed_thumbnail_url=(row.lfg_embed_thumbnail_url or "").strip() or None,
        immune_embed_enabled=bool(row.immune_embed_enabled),
        immune_embed_color=parse_embed_hex_color(
            row.immune_embed_color, default=DEFAULT_IMMUNE_EMBED_COLOR
        ),
        immune_embed_label=(row.immune_embed_label or DEFAULT_IMMUNE_EMBED_LABEL).strip()[:64],
        immune_embed_tiers=embed_tiers,
        search_penalty_enabled=bool(row.search_penalty_enabled),
        search_penalty_early_minutes=int(row.search_penalty_early_minutes or DEFAULT_EARLY_MINUTES),
        search_penalty_early_max_count=int(
            row.search_penalty_early_max_count or DEFAULT_EARLY_MAX_COUNT
        ),
        search_penalty_mid_minutes=int(row.search_penalty_mid_minutes or DEFAULT_MID_MINUTES),
        search_penalty_severe_hours=int(row.search_penalty_severe_hours or DEFAULT_SEVERE_HOURS),
        host_recreate_cooldown_seconds=int(
            row.host_recreate_cooldown_seconds or DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS
        ),
        immune_host_recreate_cooldown_seconds=int(
            row.immune_host_recreate_cooldown_seconds
            or DEFAULT_IMMUNE_HOST_RECREATE_COOLDOWN_SECONDS
        ),
        role_mappings=mapping_dict,
    )


class GuildConfigService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[int, tuple[GuildRuntimeConfig, float]] = {}

    def invalidate(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    def get_cached(self, guild_id: int) -> GuildRuntimeConfig | None:
        entry = self._cache.get(guild_id)
        if entry is None:
            return None
        config, expires_at = entry
        if time.monotonic() > expires_at:
            self._cache.pop(guild_id, None)
            return None
        return config

    def _store_cache(self, guild_id: int, config: GuildRuntimeConfig) -> GuildRuntimeConfig:
        self._cache[guild_id] = (config, time.monotonic() + CACHE_TTL_SECONDS)
        return config

    async def get_config(
        self,
        session: AsyncSession,
        guild_id: int,
    ) -> GuildRuntimeConfig:
        cached = self.get_cached(guild_id)
        if cached is not None:
            return cached

        result = await session.execute(
            select(GuildSettings).where(GuildSettings.discord_guild_id == guild_id)
        )
        row = result.scalar_one_or_none()
        mappings_result = await session.execute(
            select(GuildRoleMapping).where(GuildRoleMapping.discord_guild_id == guild_id)
        )
        mappings = list(mappings_result.scalars().all())
        config = _settings_row_to_config(guild_id, row, mappings, self._settings)
        return self._store_cache(guild_id, config)

    async def channel_allowed(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        guild_id: int | None,
        channel_id: int,
    ) -> bool:
        if guild_id is None:
            return True
        cached = self.get_cached(guild_id)
        if cached is not None:
            return cached.channel_allowed(channel_id, self._settings.lfg_channel_id_list)
        async with session_factory() as session:
            config = await self.get_config(session, guild_id)
        return config.channel_allowed(channel_id, self._settings.lfg_channel_id_list)

    async def ranking_channel_allowed(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        guild_id: int | None,
        channel_id: int,
    ) -> bool:
        if guild_id is None:
            return True
        env_lfg = self._settings.lfg_channel_id_list
        cached = self.get_cached(guild_id)
        if cached is not None:
            return cached.ranking_channel_allowed(channel_id, env_lfg)
        async with session_factory() as session:
            config = await self.get_config(session, guild_id)
        return config.ranking_channel_allowed(channel_id, env_lfg)

    async def get_config_for_factory(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        guild_id: int,
    ) -> GuildRuntimeConfig:
        cached = self.get_cached(guild_id)
        if cached is not None:
            return cached
        async with session_factory() as session:
            return await self.get_config(session, guild_id)

    async def upsert_guild(
        self,
        session: AsyncSession,
        *,
        discord_guild_id: int,
        name: str,
        bot_present: bool = True,
    ) -> None:
        result = await session.execute(
            select(Guild).where(Guild.discord_guild_id == discord_guild_id)
        )
        guild = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if guild is None:
            guild = Guild(discord_guild_id=discord_guild_id, name=name)
            session.add(guild)
            settings = GuildSettings(discord_guild_id=discord_guild_id)
            session.add(settings)
        else:
            guild.name = name
            if bot_present:
                guild.bot_removed_at = None
            else:
                guild.bot_removed_at = now
        await session.flush()

    async def ensure_default_settings(
        self,
        session: AsyncSession,
        discord_guild_id: int,
    ) -> GuildSettings:
        result = await session.execute(
            select(GuildSettings).where(GuildSettings.discord_guild_id == discord_guild_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        row = GuildSettings(discord_guild_id=discord_guild_id)
        session.add(row)
        await session.flush()
        return row

    async def seed_from_env(self, session: AsyncSession) -> None:
        guild_ids = self._settings.discord_guild_id_list
        lfg_ids = self._settings.lfg_channel_id_list
        if not guild_ids:
            return
        for guild_id in guild_ids:
            await self.upsert_guild(
                session,
                discord_guild_id=guild_id,
                name=f"Guild {guild_id}",
                bot_present=True,
            )
            settings_row = await self.ensure_default_settings(session, guild_id)
            if lfg_ids and not _int_list(settings_row.lfg_channel_ids):
                settings_row.lfg_channel_ids = lfg_ids
            if self._settings.stats_channel_id and not settings_row.stats_channel_id:
                settings_row.stats_channel_id = self._settings.stats_channel_id
            settings_row.auto_format_messages = self._settings.auto_format_messages
            settings_row.default_lfg_mode = self._settings.default_lfg_mode
            settings_row.gamification_enabled = self._settings.gamification_enabled
            settings_row.panel_sticky_enabled = self._settings.panel_sticky_enabled
            settings_row.lobby_ttl_minutes = self._settings.lobby_ttl_minutes
        self.invalidate_all()
        logger.info("seeded guild config from env for %s guild(s)", len(guild_ids))

    async def update_settings(
        self,
        session: AsyncSession,
        guild_id: int,
        *,
        lfg_channel_ids: list[int] | None = None,
        announce_channel_id: int | None | object = ...,
        auto_format_messages: bool | None = None,
        default_lfg_mode: str | None = None,
        gamification_enabled: bool | None = None,
        stats_channel_id: int | None = None,
        log_channel_id: int | None = None,
        panel_sticky_enabled: bool | None = None,
        lobby_ttl_minutes: int | None = None,
        immune_role_ids: list[int] | None = None,
        lfg_embed_color_source: str | None = None,
        rank_embed_colors: dict[str, str] | None = None,
        lfg_embed_competitive_color: str | None = None,
        lfg_embed_unrated_color: str | None = None,
        lfg_embed_full_color: str | None = None,
        lfg_embed_inactive_color: str | None = None,
        lfg_embed_decorative: bool | None = None,
        lfg_embed_footer_brand: str | None = None,
        lfg_embed_banner_url: str | None | object = ...,
        lfg_embed_custom_texts: dict[str, str] | None = None,
        lfg_embed_show_author: bool | None = None,
        lfg_embed_show_timestamp: bool | None = None,
        lfg_embed_show_thumbnail: bool | None = None,
        lfg_embed_banner_on_panel: bool | None = None,
        lfg_embed_banner_on_lobby: bool | None = None,
        lfg_panel_thumbnail_url: str | None | object = ...,
        lfg_panel_color: str | None = None,
        lfg_panel_footer_brand: str | None | object = ...,
        lfg_panel_banner_url: str | None | object = ...,
        lfg_panel_decorative: bool | None = None,
        lfg_embed_thumbnail_url: str | None | object = ...,
        immune_embed_enabled: bool | None = None,
        immune_embed_color: str | None = None,
        immune_embed_label: str | None = None,
        immune_embed_tiers: list[dict[str, Any]] | None = None,
        search_penalty_enabled: bool | None = None,
        search_penalty_early_minutes: int | None = None,
        search_penalty_early_max_count: int | None = None,
        search_penalty_mid_minutes: int | None = None,
        search_penalty_severe_hours: int | None = None,
        host_recreate_cooldown_seconds: int | None = None,
        immune_host_recreate_cooldown_seconds: int | None = None,
    ) -> GuildSettings:
        row = await self.ensure_default_settings(session, guild_id)
        if lfg_channel_ids is not None:
            row.lfg_channel_ids = lfg_channel_ids
        if announce_channel_id is not ...:
            row.announce_channel_id = announce_channel_id  # type: ignore[assignment]
        if auto_format_messages is not None:
            row.auto_format_messages = auto_format_messages
        if default_lfg_mode is not None:
            row.default_lfg_mode = default_lfg_mode
        if gamification_enabled is not None:
            row.gamification_enabled = gamification_enabled
        if stats_channel_id is not None:
            row.stats_channel_id = stats_channel_id
        if log_channel_id is not None:
            row.log_channel_id = max(0, int(log_channel_id))
        if panel_sticky_enabled is not None:
            row.panel_sticky_enabled = panel_sticky_enabled
        if lobby_ttl_minutes is not None:
            row.lobby_ttl_minutes = lobby_ttl_minutes
        if immune_role_ids is not None:
            row.immune_role_ids = immune_role_ids
        if lfg_embed_color_source is not None:
            row.lfg_embed_color_source = (
                lfg_embed_color_source
                if lfg_embed_color_source in LFG_EMBED_COLOR_SOURCES
                else "mode"
            )
        if rank_embed_colors is not None:
            row.rank_embed_colors = rank_embed_colors
        if lfg_embed_competitive_color is not None:
            row.lfg_embed_competitive_color = parse_embed_hex_color(
                lfg_embed_competitive_color, default=DEFAULT_COMPETITIVE_COLOR
            )
        if lfg_embed_unrated_color is not None:
            row.lfg_embed_unrated_color = parse_embed_hex_color(
                lfg_embed_unrated_color, default=DEFAULT_UNRATED_COLOR
            )
        if lfg_embed_full_color is not None:
            row.lfg_embed_full_color = parse_embed_hex_color(
                lfg_embed_full_color, default=DEFAULT_FULL_COLOR
            )
        if lfg_embed_inactive_color is not None:
            row.lfg_embed_inactive_color = parse_embed_hex_color(
                lfg_embed_inactive_color, default=DEFAULT_INACTIVE_COLOR
            )
        if lfg_embed_decorative is not None:
            row.lfg_embed_decorative = lfg_embed_decorative
        if lfg_embed_footer_brand is not None:
            brand = lfg_embed_footer_brand.strip()[:64] or DEFAULT_FOOTER_BRAND
            row.lfg_embed_footer_brand = brand
        if lfg_embed_banner_url is not ...:
            if lfg_embed_banner_url is None or not str(lfg_embed_banner_url).strip():
                row.lfg_embed_banner_url = None
            else:
                row.lfg_embed_banner_url = str(lfg_embed_banner_url).strip()[:2048]
        if lfg_embed_custom_texts is not None:
            row.lfg_embed_custom_texts = normalize_lfg_embed_custom_texts(lfg_embed_custom_texts)
        if lfg_embed_show_author is not None:
            row.lfg_embed_show_author = lfg_embed_show_author
        if lfg_embed_show_timestamp is not None:
            row.lfg_embed_show_timestamp = lfg_embed_show_timestamp
        if lfg_embed_show_thumbnail is not None:
            row.lfg_embed_show_thumbnail = lfg_embed_show_thumbnail
        if lfg_embed_banner_on_panel is not None:
            row.lfg_embed_banner_on_panel = lfg_embed_banner_on_panel
        if lfg_embed_banner_on_lobby is not None:
            row.lfg_embed_banner_on_lobby = lfg_embed_banner_on_lobby
        if lfg_panel_thumbnail_url is not ...:
            if lfg_panel_thumbnail_url is None or not str(lfg_panel_thumbnail_url).strip():
                row.lfg_panel_thumbnail_url = None
            else:
                row.lfg_panel_thumbnail_url = str(lfg_panel_thumbnail_url).strip()[:2048]
        if lfg_panel_color is not None:
            row.lfg_panel_color = parse_embed_hex_color(
                lfg_panel_color, default=DEFAULT_COMPETITIVE_COLOR
            )
        if lfg_panel_footer_brand is not ...:
            if lfg_panel_footer_brand is None or not str(lfg_panel_footer_brand).strip():
                row.lfg_panel_footer_brand = None
            else:
                row.lfg_panel_footer_brand = str(lfg_panel_footer_brand).strip()[:64]
        if lfg_panel_banner_url is not ...:
            if lfg_panel_banner_url is None or not str(lfg_panel_banner_url).strip():
                row.lfg_panel_banner_url = None
            else:
                row.lfg_panel_banner_url = str(lfg_panel_banner_url).strip()[:2048]
        if lfg_panel_decorative is not None:
            row.lfg_panel_decorative = lfg_panel_decorative
        if lfg_embed_thumbnail_url is not ...:
            if lfg_embed_thumbnail_url is None or not str(lfg_embed_thumbnail_url).strip():
                row.lfg_embed_thumbnail_url = None
            else:
                row.lfg_embed_thumbnail_url = str(lfg_embed_thumbnail_url).strip()[:2048]
        if immune_embed_enabled is not None:
            row.immune_embed_enabled = immune_embed_enabled
        if immune_embed_color is not None:
            row.immune_embed_color = parse_embed_hex_color(
                immune_embed_color, default=DEFAULT_IMMUNE_EMBED_COLOR
            )
        if immune_embed_label is not None:
            label = immune_embed_label.strip()[:64] or DEFAULT_IMMUNE_EMBED_LABEL
            row.immune_embed_label = label
        if immune_embed_tiers is not None:
            from app.services.lfg_embed_style import normalize_immune_embed_tiers

            normalized = normalize_immune_embed_tiers(immune_embed_tiers)
            row.immune_embed_tiers = [
                {
                    "label": tier.label,
                    "color": tier.color,
                    "role_ids": list(tier.role_ids),
                }
                for tier in normalized
            ]
            row.immune_role_ids = list(union_immune_role_ids_from_tiers(normalized))
        if search_penalty_enabled is not None:
            row.search_penalty_enabled = search_penalty_enabled
        if search_penalty_early_minutes is not None:
            row.search_penalty_early_minutes = max(1, min(search_penalty_early_minutes, 24 * 60))
        if search_penalty_early_max_count is not None:
            row.search_penalty_early_max_count = max(1, min(search_penalty_early_max_count, 20))
        if search_penalty_mid_minutes is not None:
            row.search_penalty_mid_minutes = max(1, min(search_penalty_mid_minutes, 24 * 60))
        if search_penalty_severe_hours is not None:
            row.search_penalty_severe_hours = max(1, min(search_penalty_severe_hours, 24 * 7))
        if host_recreate_cooldown_seconds is not None:
            row.host_recreate_cooldown_seconds = clamp_host_recreate_seconds(
                host_recreate_cooldown_seconds
            )
        if immune_host_recreate_cooldown_seconds is not None:
            row.immune_host_recreate_cooldown_seconds = clamp_host_recreate_seconds(
                immune_host_recreate_cooldown_seconds
            )
        await session.flush()
        self.invalidate(guild_id)
        return row

    async def replace_role_mappings(
        self,
        session: AsyncSession,
        guild_id: int,
        mappings: list[dict[str, Any]],
    ) -> None:
        await session.execute(
            delete(GuildRoleMapping).where(GuildRoleMapping.discord_guild_id == guild_id)
        )
        for item in mappings:
            mapping_type = str(item["mapping_type"])
            logical_key = str(item["logical_key"])
            role_id = int(item["discord_role_id"])
            if mapping_type not in MAPPING_TYPES:
                continue
            session.add(
                GuildRoleMapping(
                    discord_guild_id=guild_id,
                    mapping_type=mapping_type,
                    logical_key=logical_key,
                    discord_role_id=role_id,
                )
            )
        await session.flush()
        self.invalidate(guild_id)

    async def list_installed_guild_ids(self, session: AsyncSession) -> list[int]:
        result = await session.execute(
            select(Guild.discord_guild_id).where(Guild.bot_removed_at.is_(None))
        )
        return [int(row[0]) for row in result.all()]

    async def list_guilds_for_leaderboard(self, session: AsyncSession) -> list[GuildRuntimeConfig]:
        result = await session.execute(
            select(Guild.discord_guild_id).where(Guild.bot_removed_at.is_(None))
        )
        configs: list[GuildRuntimeConfig] = []
        for (guild_id,) in result.all():
            config = await self.get_config(session, int(guild_id))
            if config.gamification_enabled and config.stats_post_channel_ids():
                configs.append(config)
        return configs


_guild_config_service: GuildConfigService | None = None


def get_guild_config_service() -> GuildConfigService:
    global _guild_config_service
    if _guild_config_service is None:
        _guild_config_service = GuildConfigService()
    return _guild_config_service


async def purge_expired_oauth_states(session: AsyncSession, max_age_minutes: int = 15) -> None:
    from app.db.models import OAuthState

    cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
    await session.execute(delete(OAuthState).where(OAuthState.created_at < cutoff))
