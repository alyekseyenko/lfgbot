from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import User
from app.services.errors import HostRecreateBlockedError
from app.services.guild_config import GuildRuntimeConfig
from app.services.host_recreate_cooldown import (
    apply_host_recreate_cooldown,
    assert_can_host_create,
)
from app.services.lfg_embed_style import (
    LfgEmbedSimpleSettings,
    normalize_lfg_embed_detailed,
    normalize_lfg_embed_panel,
)
from app.services.lobbies import close_lobby_as_host, create_lobby


def _immune_member(role_id: int = 99) -> MagicMock:
    role = MagicMock()
    role.id = role_id
    member = MagicMock()
    member.roles = [role]
    return member


def test_guild_runtime_immune_shorter_cooldown() -> None:
    cfg = GuildRuntimeConfig(
        discord_guild_id=1,
        lfg_channel_ids=(),
        announce_channel_id=None,
        weekly_leaderboard_anchor=None,
        reputation_channel_id=0,
        reputation_delay_minutes=50,
        reputation_enabled_at=None,
        reputation_negative_threshold=-15,
        reputation_negative_role_id=0,
        reputation_positive_threshold=25,
        reputation_positive_role_id=0,
        auto_format_messages=True,
        default_lfg_mode="Competitivo",
        gamification_enabled=False,
        stats_channel_id=0,
        log_channel_id=0,
        panel_sticky_enabled=True,
        lobby_ttl_minutes=45,
        party_code_max_length=6,
        immune_role_ids=(99,),
        lfg_embed_color_source="mode",
        rank_embed_colors={},
        lfg_embed_competitive_color="FF4655",
        lfg_embed_unrated_color="5E98D9",
        lfg_embed_full_color="C23B22",
        lfg_embed_inactive_color="4A4E5A",
        lfg_embed_decorative=True,
        lfg_embed_footer_brand="LFG Valorant",
        lfg_embed_banner_url=None,
        lfg_embed_custom_texts={},
        lfg_embed_show_author=True,
        lfg_embed_show_timestamp=True,
        lfg_embed_show_thumbnail=True,
        lfg_embed_banner_on_panel=True,
        lfg_embed_banner_on_lobby=True,
        lfg_panel_thumbnail_url=None,
        lfg_panel_color="FF4655",
        lfg_panel_footer_brand=None,
        lfg_panel_banner_url=None,
        lfg_panel_decorative=True,
        lfg_embed_thumbnail_url=None,
        lfg_embed_simple=LfgEmbedSimpleSettings(),
        lfg_embed_detailed=normalize_lfg_embed_detailed({}),
        lfg_embed_panel=normalize_lfg_embed_panel({}),
        lfg_post_style_simple_enabled=True,
        lfg_post_style_detailed_enabled=True,
        immune_embed_enabled=True,
        immune_embed_color="FFD700",
        immune_embed_label="VIP",
        immune_embed_tiers=(),
        search_penalty_enabled=True,
        search_penalty_early_minutes=5,
        search_penalty_early_max_count=3,
        search_penalty_mid_minutes=15,
        search_penalty_severe_hours=12,
        host_recreate_cooldown_seconds=300,
        immune_host_recreate_cooldown_seconds=10,
        role_mappings={},
    )
    assert cfg.host_recreate_cooldown_for_member(_immune_member()) == timedelta(seconds=10)
    assert cfg.host_recreate_cooldown_for_member(None) == timedelta(seconds=300)


def test_assert_can_host_create_raises() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    user = User(discord_id=1, name="a", host_create_blocked_until=now + timedelta(minutes=5))
    with pytest.raises(HostRecreateBlockedError):
        assert_can_host_create(user, now)


@pytest.mark.asyncio
async def test_close_blocks_recreate_until_cooldown_elapsed(
    session: AsyncSession, event_bus: EventBus
) -> None:
    host = User(discord_id=50, name="host")
    session.add(host)
    await session.flush()

    lobby = await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code=None,
        expires_in=timedelta(hours=1),
    )
    await session.commit()

    now = datetime.now(UTC)
    async with session.begin():
        await close_lobby_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=50,
            now=now,
            host_recreate_cooldown=timedelta(minutes=5),
        )

    async with session.begin():
        host_row = await session.get(User, 50)
        assert host_row is not None
        with pytest.raises(HostRecreateBlockedError):
            assert_can_host_create(host_row, now + timedelta(seconds=30))


@pytest.mark.asyncio
async def test_replace_close_without_cooldown_allows_immediate_create(
    session: AsyncSession, event_bus: EventBus
) -> None:
    host = User(discord_id=51, name="host")
    session.add(host)
    await session.flush()

    lobby = await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code=None,
        expires_in=timedelta(hours=1),
    )
    await session.commit()

    now = datetime.now(UTC)
    async with session.begin():
        await close_lobby_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=51,
            now=now,
            host_recreate_cooldown=timedelta(seconds=10),
            apply_host_recreate_cooldown_on_close=False,
        )
        host_row = await session.get(User, 51)
        assert host_row is not None
        assert host_row.host_create_blocked_until is None
        await create_lobby(
            session,
            event_bus,
            host=host_row,
            mode="Unrated",
            slots=3,
            party_code=None,
            expires_in=timedelta(hours=1),
        )


def test_apply_host_recreate_cooldown_replaces_block_on_close() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    user = User(
        discord_id=2,
        name="b",
        host_create_blocked_until=now + timedelta(hours=1),
    )
    apply_host_recreate_cooldown(user, now, timedelta(seconds=10))
    assert user.host_create_blocked_until == now + timedelta(seconds=10)
