from __future__ import annotations

import logging
from urllib.parse import urlencode

import discord
import httpx
from discord.ext import commands
from fastapi import APIRouter, HTTPException

from app.api.deps import ApiStateDep, BotDep, SessionUserDep
from app.api.discord_api import fetch_user_guilds, user_can_manage_guild
from app.api.guild_cache import get_discord_guilds
from app.api.schemas import (
    CreatorLevelItem,
    CreatorLevelsPut,
    DiscordChannelOut,
    DiscordRoleOut,
    GuildOut,
    GuildSettingsOut,
    GuildSettingsPatch,
    GuildStatsOut,
    ImmuneEmbedTierOut,
    InviteUrlOut,
    RoleMappingItem,
    RoleMappingsPut,
    ValorantAgentRoleItem,
    ValorantAgentRolesPut,
)
from app.api.snowflake import (
    parse_snowflake,
    parse_snowflake_list,
    snowflake_list_to_str,
    snowflake_to_str,
)
from app.api.state import ApiState
from app.services.creator_levels import (
    CreatorLevelDef,
    ensure_default_creator_levels,
    normalize_level_payload,
    replace_creator_levels,
)
from app.services.guide_content import normalize_guide_body
from app.services.guild_stats import guild_lobby_stats, guild_lobby_stats_lifetime
from app.services.guild_valorant_agents import (
    list_guild_agent_role_mappings,
    replace_guild_agent_role_mappings,
)
from app.services.lfg_embed_style import (
    DEFAULT_IMMUNE_EMBED_COLOR,
    DEFAULT_IMMUNE_EMBED_LABEL,
    immune_embed_tiers_for_config,
    lfg_embed_detailed_to_storage,
    lfg_embed_panel_to_storage,
    lfg_embed_simple_to_storage,
    normalize_lfg_embed_custom_texts,
    normalize_lfg_embed_detailed,
    normalize_lfg_embed_panel,
    normalize_lfg_embed_simple,
    normalize_rank_embed_colors,
    parse_embed_hex_color,
)
from app.services.settings_audit import (
    build_dashboard_settings_audit,
    filter_changed_settings_patch,
)

router = APIRouter(tags=["guilds"])
logger = logging.getLogger(__name__)


async def _user_guilds_from_discord(user: dict) -> list[dict]:
    user_id = int(user["id"])
    access_token = str(user["access_token"])

    async def fetch() -> list[dict]:
        return await fetch_user_guilds(access_token)

    try:
        return await get_discord_guilds(user_id, fetch)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=503,
                detail="Discord limitou pedidos. Espera alguns segundos e atualiza a página.",
            ) from exc
        raise HTTPException(
            status_code=502, detail="Falha ao obter servidores do Discord."
        ) from exc


async def _assert_manage_guild(user: dict, guild_id: int) -> None:
    guilds = await _user_guilds_from_discord(user)
    match = next((g for g in guilds if int(g["id"]) == guild_id), None)
    if match is None or not user_can_manage_guild(match):
        raise HTTPException(status_code=403, detail="Sem permissão para gerir este servidor.")


def _int_list(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _immune_embed_tiers_out(row) -> list[ImmuneEmbedTierOut]:
    legacy_ids = tuple(_int_list(row.immune_role_ids))
    tiers = immune_embed_tiers_for_config(
        row.immune_embed_tiers,
        legacy_role_ids=legacy_ids,
        legacy_label=(row.immune_embed_label or DEFAULT_IMMUNE_EMBED_LABEL),
        legacy_color=row.immune_embed_color or DEFAULT_IMMUNE_EMBED_COLOR,
    )
    return [
        ImmuneEmbedTierOut(
            label=tier.label,
            color=tier.color,
            role_ids=snowflake_list_to_str(list(tier.role_ids)),
        )
        for tier in tiers
    ]


def _settings_to_out(row) -> GuildSettingsOut:
    lfg = row.lfg_channel_ids if isinstance(row.lfg_channel_ids, list) else []
    immune = row.immune_role_ids if isinstance(row.immune_role_ids, list) else []
    announce = row.announce_channel_id
    return GuildSettingsOut(
        lfg_channel_ids=snowflake_list_to_str(lfg),
        announce_channel_id=snowflake_to_str(announce) if announce else None,
        weekly_leaderboard_anchor=(
            row.weekly_leaderboard_anchor.isoformat()
            if getattr(row, "weekly_leaderboard_anchor", None)
            else None
        ),
        reputation_channel_id=snowflake_to_str(int(row.reputation_channel_id or 0)),
        reputation_delay_minutes=int(row.reputation_delay_minutes or 50),
        reputation_negative_threshold=int(row.reputation_negative_threshold or -15),
        reputation_negative_role_id=snowflake_to_str(int(row.reputation_negative_role_id or 0)),
        reputation_positive_threshold=int(row.reputation_positive_threshold or 25),
        reputation_positive_role_id=snowflake_to_str(int(row.reputation_positive_role_id or 0)),
        auto_format_messages=row.auto_format_messages,
        default_lfg_mode=row.default_lfg_mode,
        gamification_enabled=row.gamification_enabled,
        stats_channel_id=snowflake_to_str(int(row.stats_channel_id or 0)),
        log_channel_id=snowflake_to_str(int(row.log_channel_id or 0)),
        panel_sticky_enabled=row.panel_sticky_enabled,
        lobby_ttl_minutes=row.lobby_ttl_minutes,
        party_code_max_length=int(row.party_code_max_length),
        immune_role_ids=snowflake_list_to_str(immune),
        lfg_embed_color_source=row.lfg_embed_color_source or "mode",
        rank_embed_colors=normalize_rank_embed_colors(row.rank_embed_colors),
        lfg_embed_competitive_color=parse_embed_hex_color(
            row.lfg_embed_competitive_color, default="FF4655"
        ),
        lfg_embed_unrated_color=parse_embed_hex_color(
            row.lfg_embed_unrated_color, default="5E98D9"
        ),
        lfg_embed_full_color=parse_embed_hex_color(row.lfg_embed_full_color, default="C23B22"),
        lfg_embed_inactive_color=parse_embed_hex_color(
            row.lfg_embed_inactive_color, default="4A4E5A"
        ),
        lfg_embed_decorative=bool(row.lfg_embed_decorative),
        lfg_embed_footer_brand=(row.lfg_embed_footer_brand or "LFG Valorant").strip()[:64]
        or "LFG Valorant",
        lfg_embed_banner_url=(row.lfg_embed_banner_url or "").strip() or None,
        lfg_embed_custom_texts=normalize_lfg_embed_custom_texts(row.lfg_embed_custom_texts),
        lfg_embed_show_author=bool(row.lfg_embed_show_author),
        lfg_embed_show_timestamp=bool(row.lfg_embed_show_timestamp),
        lfg_embed_show_thumbnail=bool(row.lfg_embed_show_thumbnail),
        lfg_embed_banner_on_panel=bool(row.lfg_embed_banner_on_panel),
        lfg_embed_banner_on_lobby=bool(row.lfg_embed_banner_on_lobby),
        lfg_panel_thumbnail_url=(row.lfg_panel_thumbnail_url or "").strip() or None,
        lfg_panel_color=parse_embed_hex_color(row.lfg_panel_color, default="FF4655"),
        lfg_panel_footer_brand=(row.lfg_panel_footer_brand or "").strip()[:64] or None,
        lfg_panel_banner_url=(row.lfg_panel_banner_url or "").strip() or None,
        lfg_panel_decorative=bool(row.lfg_panel_decorative),
        lfg_embed_thumbnail_url=(row.lfg_embed_thumbnail_url or "").strip() or None,
        lfg_embed_simple=lfg_embed_simple_to_storage(
            normalize_lfg_embed_simple(
                row.lfg_embed_simple,
                fallback_footer_brand=(row.lfg_embed_footer_brand or "LFG Valorant"),
            )
        ),
        lfg_embed_detailed=lfg_embed_detailed_to_storage(
            normalize_lfg_embed_detailed(row.lfg_embed_detailed)
        ),
        lfg_embed_panel=lfg_embed_panel_to_storage(normalize_lfg_embed_panel(row.lfg_embed_panel)),
        lfg_post_style_simple_enabled=bool(row.lfg_post_style_simple_enabled),
        lfg_post_style_detailed_enabled=bool(row.lfg_post_style_detailed_enabled),
        immune_embed_enabled=bool(row.immune_embed_enabled),
        immune_embed_color=parse_embed_hex_color(
            row.immune_embed_color, default=DEFAULT_IMMUNE_EMBED_COLOR
        ),
        immune_embed_label=(row.immune_embed_label or DEFAULT_IMMUNE_EMBED_LABEL).strip()[:64],
        immune_embed_tiers=_immune_embed_tiers_out(row),
        search_penalty_enabled=bool(row.search_penalty_enabled),
        search_penalty_early_minutes=int(row.search_penalty_early_minutes or 5),
        search_penalty_early_max_count=int(row.search_penalty_early_max_count or 3),
        search_penalty_mid_minutes=int(row.search_penalty_mid_minutes or 15),
        search_penalty_severe_hours=int(row.search_penalty_severe_hours or 12),
        host_recreate_cooldown_seconds=int(row.host_recreate_cooldown_seconds or 300),
        immune_host_recreate_cooldown_seconds=int(row.immune_host_recreate_cooldown_seconds or 10),
        guide_channel_id=snowflake_to_str(int(row.guide_channel_id or 0)),
        guide_body=row.guide_body,
        stats_legacy_lobbies_created=int(row.stats_legacy_lobbies_created or 0),
        stats_legacy_joins=int(row.stats_legacy_joins or 0),
        stats_legacy_users=int(row.stats_legacy_users or 0),
    )


def _primary_manage_guild_id(state: ApiState) -> int | None:
    ids = state.settings.discord_guild_id_list
    return ids[0] if ids else None


def _guild_id_param(guild_id: str) -> int:
    return parse_snowflake(guild_id, field="guild_id")


@router.get("/invite-url", response_model=InviteUrlOut)
async def invite_url(state: ApiStateDep) -> InviteUrlOut:
    if not state.settings.discord_application_id:
        raise HTTPException(status_code=503, detail="DISCORD_APPLICATION_ID em falta.")
    params = {
        "client_id": state.settings.discord_application_id,
        "permissions": "268435456",
        "scope": "bot applications.commands",
    }
    return InviteUrlOut(url=f"https://discord.com/api/oauth2/authorize?{urlencode(params)}")


@router.get("/guilds", response_model=list[GuildOut])
async def list_guilds(
    state: ApiStateDep,
    user: SessionUserDep,
    bot: BotDep,
) -> list[GuildOut]:
    guilds = await _user_guilds_from_discord(user)
    manageable = [g for g in guilds if user_can_manage_guild(g)]
    # Só marcar instalado se o bot está na cache do gateway (evita «instalado» na BD
    # mas 404 ao listar canais).
    bot_guild_ids = {g.id for g in bot.guilds}
    out: list[GuildOut] = []
    for g in manageable:
        gid = int(g["id"])
        out.append(
            GuildOut(
                id=str(gid),
                name=str(g.get("name", "")),
                icon=g.get("icon"),
                bot_installed=gid in bot_guild_ids,
            )
        )
    out.sort(key=lambda item: (not item.bot_installed, item.name.lower()))
    return out


@router.get("/guilds/{guild_id}/settings", response_model=GuildSettingsOut)
async def get_settings(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
) -> GuildSettingsOut:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        async with session.begin():
            await state.guild_config.upsert_guild(
                session, discord_guild_id=gid, name=f"Guild {gid}"
            )
            row = await state.guild_config.ensure_default_settings(session, gid)
        return _settings_to_out(row)


@router.patch("/guilds/{guild_id}/settings", response_model=GuildSettingsOut)
async def patch_settings(
    guild_id: str,
    body: GuildSettingsPatch,
    state: ApiStateDep,
    user: SessionUserDep,
) -> GuildSettingsOut:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    patch_kwargs: dict = {}
    if body.lfg_channel_ids is not None:
        patch_kwargs["lfg_channel_ids"] = parse_snowflake_list(body.lfg_channel_ids)
    if body.announce_channel_id is not None:
        patch_kwargs["announce_channel_id"] = (
            None
            if body.announce_channel_id in ("", "0")
            else parse_snowflake(body.announce_channel_id, field="announce_channel_id")
        )
    if body.weekly_leaderboard_anchor is not None:
        from datetime import date as date_type

        raw_anchor = body.weekly_leaderboard_anchor.strip()
        if raw_anchor in ("", "0"):
            patch_kwargs["weekly_leaderboard_anchor"] = None
        else:
            try:
                patch_kwargs["weekly_leaderboard_anchor"] = date_type.fromisoformat(raw_anchor)
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail="weekly_leaderboard_anchor tem de ser YYYY-MM-DD.",
                ) from None
    if body.reputation_channel_id is not None:
        patch_kwargs["reputation_channel_id"] = (
            0
            if body.reputation_channel_id in ("", "0")
            else parse_snowflake(body.reputation_channel_id, field="reputation_channel_id")
        )
    if body.reputation_delay_minutes is not None:
        patch_kwargs["reputation_delay_minutes"] = body.reputation_delay_minutes
    if body.reputation_negative_threshold is not None:
        patch_kwargs["reputation_negative_threshold"] = body.reputation_negative_threshold
    if body.reputation_negative_role_id is not None:
        patch_kwargs["reputation_negative_role_id"] = (
            0
            if body.reputation_negative_role_id in ("", "0")
            else parse_snowflake(
                body.reputation_negative_role_id, field="reputation_negative_role_id"
            )
        )
    if body.reputation_positive_threshold is not None:
        patch_kwargs["reputation_positive_threshold"] = body.reputation_positive_threshold
    if body.reputation_positive_role_id is not None:
        patch_kwargs["reputation_positive_role_id"] = (
            0
            if body.reputation_positive_role_id in ("", "0")
            else parse_snowflake(
                body.reputation_positive_role_id, field="reputation_positive_role_id"
            )
        )
    if body.auto_format_messages is not None:
        patch_kwargs["auto_format_messages"] = body.auto_format_messages
    if body.default_lfg_mode is not None:
        patch_kwargs["default_lfg_mode"] = body.default_lfg_mode
    if body.gamification_enabled is not None:
        patch_kwargs["gamification_enabled"] = body.gamification_enabled
    if body.stats_channel_id is not None:
        patch_kwargs["stats_channel_id"] = parse_snowflake(
            body.stats_channel_id, field="stats_channel_id"
        )
    if body.log_channel_id is not None:
        patch_kwargs["log_channel_id"] = (
            0
            if body.log_channel_id in ("", "0")
            else parse_snowflake(body.log_channel_id, field="log_channel_id")
        )
    if body.panel_sticky_enabled is not None:
        patch_kwargs["panel_sticky_enabled"] = body.panel_sticky_enabled
    if body.lobby_ttl_minutes is not None:
        patch_kwargs["lobby_ttl_minutes"] = body.lobby_ttl_minutes
    if body.party_code_max_length is not None:
        patch_kwargs["party_code_max_length"] = body.party_code_max_length
    if body.immune_role_ids is not None:
        patch_kwargs["immune_role_ids"] = parse_snowflake_list(body.immune_role_ids)
    if body.lfg_embed_color_source is not None:
        patch_kwargs["lfg_embed_color_source"] = body.lfg_embed_color_source
    if body.rank_embed_colors is not None:
        patch_kwargs["rank_embed_colors"] = normalize_rank_embed_colors(body.rank_embed_colors)
    if body.lfg_embed_competitive_color is not None:
        patch_kwargs["lfg_embed_competitive_color"] = body.lfg_embed_competitive_color
    if body.lfg_embed_unrated_color is not None:
        patch_kwargs["lfg_embed_unrated_color"] = body.lfg_embed_unrated_color
    if body.lfg_embed_full_color is not None:
        patch_kwargs["lfg_embed_full_color"] = body.lfg_embed_full_color
    if body.lfg_embed_inactive_color is not None:
        patch_kwargs["lfg_embed_inactive_color"] = body.lfg_embed_inactive_color
    if body.lfg_embed_decorative is not None:
        patch_kwargs["lfg_embed_decorative"] = body.lfg_embed_decorative
    if body.lfg_embed_footer_brand is not None:
        patch_kwargs["lfg_embed_footer_brand"] = body.lfg_embed_footer_brand.strip()[:64]
    if body.lfg_embed_banner_url is not None:
        patch_kwargs["lfg_embed_banner_url"] = body.lfg_embed_banner_url.strip() or None
    if body.lfg_embed_custom_texts is not None:
        patch_kwargs["lfg_embed_custom_texts"] = normalize_lfg_embed_custom_texts(
            body.lfg_embed_custom_texts
        )
    if body.lfg_embed_show_author is not None:
        patch_kwargs["lfg_embed_show_author"] = body.lfg_embed_show_author
    if body.lfg_embed_show_timestamp is not None:
        patch_kwargs["lfg_embed_show_timestamp"] = body.lfg_embed_show_timestamp
    if body.lfg_embed_show_thumbnail is not None:
        patch_kwargs["lfg_embed_show_thumbnail"] = body.lfg_embed_show_thumbnail
    if body.lfg_embed_banner_on_panel is not None:
        patch_kwargs["lfg_embed_banner_on_panel"] = body.lfg_embed_banner_on_panel
    if body.lfg_embed_banner_on_lobby is not None:
        patch_kwargs["lfg_embed_banner_on_lobby"] = body.lfg_embed_banner_on_lobby
    if body.lfg_panel_thumbnail_url is not None:
        patch_kwargs["lfg_panel_thumbnail_url"] = body.lfg_panel_thumbnail_url.strip() or None
    if body.lfg_panel_color is not None:
        patch_kwargs["lfg_panel_color"] = body.lfg_panel_color
    if body.lfg_panel_footer_brand is not None:
        patch_kwargs["lfg_panel_footer_brand"] = body.lfg_panel_footer_brand.strip() or None
    if body.lfg_panel_banner_url is not None:
        patch_kwargs["lfg_panel_banner_url"] = body.lfg_panel_banner_url.strip() or None
    if body.lfg_panel_decorative is not None:
        patch_kwargs["lfg_panel_decorative"] = body.lfg_panel_decorative
    if body.lfg_embed_thumbnail_url is not None:
        patch_kwargs["lfg_embed_thumbnail_url"] = body.lfg_embed_thumbnail_url.strip() or None
    if body.lfg_embed_simple is not None:
        patch_kwargs["lfg_embed_simple"] = body.lfg_embed_simple
    if body.lfg_embed_detailed is not None:
        patch_kwargs["lfg_embed_detailed"] = body.lfg_embed_detailed
    if body.lfg_embed_panel is not None:
        patch_kwargs["lfg_embed_panel"] = body.lfg_embed_panel
    if body.lfg_post_style_simple_enabled is not None:
        patch_kwargs["lfg_post_style_simple_enabled"] = body.lfg_post_style_simple_enabled
    if body.lfg_post_style_detailed_enabled is not None:
        patch_kwargs["lfg_post_style_detailed_enabled"] = body.lfg_post_style_detailed_enabled
    if body.immune_embed_enabled is not None:
        patch_kwargs["immune_embed_enabled"] = body.immune_embed_enabled
    if body.immune_embed_color is not None:
        patch_kwargs["immune_embed_color"] = body.immune_embed_color
    if body.immune_embed_label is not None:
        patch_kwargs["immune_embed_label"] = body.immune_embed_label.strip()[:64]
    if body.immune_embed_tiers is not None:
        tiers_payload: list[dict] = []
        for tier in body.immune_embed_tiers[:5]:
            tiers_payload.append(
                {
                    "label": (tier.label or DEFAULT_IMMUNE_EMBED_LABEL).strip()[:64],
                    "color": parse_embed_hex_color(tier.color, default=DEFAULT_IMMUNE_EMBED_COLOR),
                    "role_ids": parse_snowflake_list(tier.role_ids),
                }
            )
        patch_kwargs["immune_embed_tiers"] = tiers_payload
    if body.search_penalty_enabled is not None:
        patch_kwargs["search_penalty_enabled"] = body.search_penalty_enabled
    if body.search_penalty_early_minutes is not None:
        patch_kwargs["search_penalty_early_minutes"] = body.search_penalty_early_minutes
    if body.search_penalty_early_max_count is not None:
        patch_kwargs["search_penalty_early_max_count"] = body.search_penalty_early_max_count
    if body.search_penalty_mid_minutes is not None:
        patch_kwargs["search_penalty_mid_minutes"] = body.search_penalty_mid_minutes
    if body.search_penalty_severe_hours is not None:
        patch_kwargs["search_penalty_severe_hours"] = body.search_penalty_severe_hours
    if body.host_recreate_cooldown_seconds is not None:
        patch_kwargs["host_recreate_cooldown_seconds"] = body.host_recreate_cooldown_seconds
    if body.immune_host_recreate_cooldown_seconds is not None:
        patch_kwargs["immune_host_recreate_cooldown_seconds"] = (
            body.immune_host_recreate_cooldown_seconds
        )
    if body.guide_channel_id is not None:
        patch_kwargs["guide_channel_id"] = (
            0
            if body.guide_channel_id in ("", "0")
            else parse_snowflake(body.guide_channel_id, field="guide_channel_id")
        )
    if body.guide_body is not None:
        patch_kwargs["guide_body"] = normalize_guide_body(body.guide_body)
    if body.stats_legacy_lobbies_created is not None:
        patch_kwargs["stats_legacy_lobbies_created"] = body.stats_legacy_lobbies_created
    if body.stats_legacy_joins is not None:
        patch_kwargs["stats_legacy_joins"] = body.stats_legacy_joins
    if body.stats_legacy_users is not None:
        patch_kwargs["stats_legacy_users"] = body.stats_legacy_users
    async with state.session_factory() as session:
        async with session.begin():
            await state.guild_config.upsert_guild(
                session, discord_guild_id=gid, name=f"Guild {gid}"
            )
            row = await state.guild_config.ensure_default_settings(session, gid)
            changed_kwargs = filter_changed_settings_patch(row, patch_kwargs)
            if changed_kwargs:
                row = await state.guild_config.update_settings(session, gid, **changed_kwargs)
        out = _settings_to_out(row)
    panel_fields_changed = bool(
        changed_kwargs
        and (
            "panel_sticky_enabled" in changed_kwargs
            or "lfg_channel_ids" in changed_kwargs
            or "lfg_embed_panel" in changed_kwargs
            or "lfg_embed_custom_texts" in changed_kwargs
            or "lfg_panel_thumbnail_url" in changed_kwargs
            or "lfg_panel_color" in changed_kwargs
            or "lfg_panel_footer_brand" in changed_kwargs
            or "lfg_panel_banner_url" in changed_kwargs
            or "lfg_panel_decorative" in changed_kwargs
            or "lfg_embed_banner_on_panel" in changed_kwargs
            or "guide_channel_id" in changed_kwargs
        )
    )
    if (
        out.panel_sticky_enabled
        and panel_fields_changed
        and isinstance(state.bot, commands.Bot)
        and state.bot.is_ready()
    ):
        from app.bot.lfg_panel import ensure_guild_lfg_panels

        try:
            posted = await ensure_guild_lfg_panels(
                state.bot,
                state.settings,
                state.session_factory,
                state.event_bus,
                state.guild_config,
                gid,
            )
            if posted:
                logger.info(
                    "painel LFG sincronizado após settings (%s canal/is) no servidor %s",
                    posted,
                    gid,
                )
        except Exception:
            logger.exception("falha ao sincronizar painel LFG no servidor %s", gid)
    guide_sync = changed_kwargs and (
        "guide_channel_id" in changed_kwargs or "guide_body" in changed_kwargs
    )
    if (
        guide_sync
        and (out.guide_channel_id or "0") not in ("", "0")
        and isinstance(state.bot, commands.Bot)
        and state.bot.is_ready()
    ):
        from app.bot.guide_channel import publish_guild_guide

        try:
            await publish_guild_guide(state.bot, state.session_factory, gid)
        except Exception:
            logger.exception("falha ao publicar guia LFG no servidor %s", gid)
    if changed_kwargs and isinstance(state.bot, discord.Client) and state.bot.is_ready():
        from app.bot.guild_audit_log import send_guild_audit_log

        username = str(user.get("username", "admin"))
        try:
            user_id_raw = user.get("id")
            user_id = int(user_id_raw) if user_id_raw is not None else None
        except (TypeError, ValueError):
            user_id = None
        title, description, fields = build_dashboard_settings_audit(
            changed_kwargs,
            username=username,
            user_id=user_id,
        )
        try:
            await send_guild_audit_log(
                state.bot,
                state.guild_config,
                state.session_factory,
                gid,
                title=title,
                description=description,
                fields=fields,
                colour=discord.Colour.from_rgb(88, 101, 242),
            )
        except Exception:
            logger.exception("falha ao enviar audit log de settings no servidor %s", gid)
    return out


@router.get("/guilds/{guild_id}/discord-roles", response_model=list[DiscordRoleOut])
async def list_discord_roles(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
    bot: BotDep,
) -> list[DiscordRoleOut]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    guild = bot.get_guild(gid)
    if guild is None:
        raise HTTPException(status_code=404, detail="O bot não está neste servidor.")
    roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
    return [
        DiscordRoleOut(
            id=str(role.id), name=role.name, color=role.color.value, position=role.position
        )
        for role in roles
        if role.name != "@everyone"
    ]


@router.get("/guilds/{guild_id}/discord-channels", response_model=list[DiscordChannelOut])
async def list_discord_channels(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
    bot: BotDep,
) -> list[DiscordChannelOut]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    guild = bot.get_guild(gid)
    if guild is None:
        raise HTTPException(status_code=404, detail="O bot não está neste servidor.")
    channels: list[DiscordChannelOut] = []
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            channels.append(
                DiscordChannelOut(
                    id=str(channel.id), name=channel.name, type=int(channel.type.value)
                )
            )
    channels.sort(key=lambda c: c.name.lower())
    return channels


@router.get("/guilds/{guild_id}/role-mappings", response_model=list[RoleMappingItem])
async def get_role_mappings(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[RoleMappingItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        config = await state.guild_config.get_config(session, gid)
    return [
        RoleMappingItem(
            mapping_type=mtype,
            logical_key=key,
            discord_role_id=str(role_id),
        )
        for (mtype, key), role_id in config.role_mappings.items()
    ]


@router.put("/guilds/{guild_id}/role-mappings", response_model=list[RoleMappingItem])
async def put_role_mappings(
    guild_id: str,
    body: RoleMappingsPut,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[RoleMappingItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    payload = [
        {
            "mapping_type": m.mapping_type,
            "logical_key": m.logical_key,
            "discord_role_id": parse_snowflake(m.discord_role_id, field="discord_role_id"),
        }
        for m in body.mappings
    ]
    async with state.session_factory() as session:
        async with session.begin():
            await state.guild_config.replace_role_mappings(session, gid, payload)
            config = await state.guild_config.get_config(session, gid)
    return [
        RoleMappingItem(mapping_type=mtype, logical_key=key, discord_role_id=str(role_id))
        for (mtype, key), role_id in config.role_mappings.items()
    ]


@router.get("/guilds/{guild_id}/valorant-agent-roles", response_model=list[ValorantAgentRoleItem])
async def get_valorant_agent_roles(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[ValorantAgentRoleItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        rows = await list_guild_agent_role_mappings(session, gid)
    return [
        ValorantAgentRoleItem(
            agent_uuid=row.agent_uuid,
            discord_role_id=str(row.discord_role_id),
        )
        for row in rows
    ]


@router.put("/guilds/{guild_id}/valorant-agent-roles", response_model=list[ValorantAgentRoleItem])
async def put_valorant_agent_roles(
    guild_id: str,
    body: ValorantAgentRolesPut,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[ValorantAgentRoleItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    payload = [
        (
            m.agent_uuid.strip(),
            parse_snowflake(m.discord_role_id, field="discord_role_id"),
        )
        for m in body.mappings
        if m.agent_uuid.strip()
    ]
    async with state.session_factory() as session:
        async with session.begin():
            rows = await replace_guild_agent_role_mappings(session, gid, payload)
    return [
        ValorantAgentRoleItem(
            agent_uuid=row.agent_uuid,
            discord_role_id=str(row.discord_role_id),
        )
        for row in rows
    ]


def _creator_levels_out(levels: list[CreatorLevelDef]) -> list[CreatorLevelItem]:
    return [
        CreatorLevelItem(
            level_number=item.level_number,
            name=item.name,
            min_rooms=item.min_rooms,
            discord_role_id=str(item.discord_role_id) if item.discord_role_id else None,
        )
        for item in levels
    ]


@router.get("/guilds/{guild_id}/creator-levels", response_model=list[CreatorLevelItem])
async def get_creator_levels(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[CreatorLevelItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        async with session.begin():
            await state.guild_config.ensure_default_settings(session, gid)
            levels = await ensure_default_creator_levels(session, gid)
    return _creator_levels_out(levels)


@router.put("/guilds/{guild_id}/creator-levels", response_model=list[CreatorLevelItem])
async def put_creator_levels(
    guild_id: str,
    body: CreatorLevelsPut,
    state: ApiStateDep,
    user: SessionUserDep,
) -> list[CreatorLevelItem]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    try:
        payload = normalize_level_payload([item.model_dump() for item in body.levels])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    async with state.session_factory() as session:
        async with session.begin():
            await state.guild_config.ensure_default_settings(session, gid)
            levels = await replace_creator_levels(session, gid, payload)
    return _creator_levels_out(levels)


@router.post("/guilds/{guild_id}/guide/publish")
async def publish_guild_guide_route(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
) -> dict[str, str]:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    if not isinstance(state.bot, commands.Bot) or not state.bot.is_ready():
        raise HTTPException(status_code=503, detail="O bot Discord não está ligado.")
    async with state.session_factory() as session:
        row = await state.guild_config.ensure_default_settings(session, gid)
        if int(row.guide_channel_id or 0) <= 0:
            raise HTTPException(status_code=400, detail="Canal do guia não configurado.")
    from app.bot.guide_channel import publish_guild_guide

    ok = await publish_guild_guide(state.bot, state.session_factory, gid)
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível publicar no canal (permissões ou canal inválido).",
        )
    return {"status": "ok"}


@router.get("/guilds/{guild_id}/stats", response_model=GuildStatsOut)
async def guild_stats(
    guild_id: str,
    state: ApiStateDep,
    user: SessionUserDep,
    days: int = 30,
) -> GuildStatsOut:
    gid = _guild_id_param(guild_id)
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        config = await state.guild_config.get_config(session, gid)
        row = await state.guild_config.ensure_default_settings(session, gid)
        stats = await guild_lobby_stats(
            session,
            discord_guild_id=gid,
            channel_ids=list(config.lfg_channel_ids),
            days=days,
        )
        lifetime = await guild_lobby_stats_lifetime(
            session,
            discord_guild_id=gid,
            channel_ids=list(config.lfg_channel_ids),
            legacy_lobbies=int(row.stats_legacy_lobbies_created or 0),
            legacy_joins=int(row.stats_legacy_joins or 0),
            legacy_users=int(row.stats_legacy_users or 0),
        )
    by_source = stats["created_by_source"]
    return GuildStatsOut(
        active_lobbies=int(stats["active_lobbies"]),
        lobbies_created_period=int(stats["lobbies_created_period"]),
        joins_period=int(stats["joins_period"]),
        active_users_7d=int(stats["active_users_7d"]),
        groups_filled_period=int(stats["groups_filled_period"]),
        groups_completed_period=int(stats["groups_completed_period"]),
        avg_minutes_to_fill=float(stats["avg_minutes_to_fill"]),
        avg_minutes_to_end=float(stats["avg_minutes_to_end"]),
        created_by_source=by_source,
        period_days=days,
        lobbies_created_lifetime=int(lifetime["lobbies_created_lifetime"]),
        joins_lifetime=int(lifetime["joins_lifetime"]),
        users_lifetime=int(lifetime["users_lifetime"]),
        lobbies_created_bot=int(lifetime["lobbies_created_bot"]),
        joins_bot=int(lifetime["joins_bot"]),
        users_bot=int(lifetime["users_bot"]),
        stats_legacy_lobbies_created=int(row.stats_legacy_lobbies_created or 0),
        stats_legacy_joins=int(row.stats_legacy_joins or 0),
        stats_legacy_users=int(row.stats_legacy_users or 0),
    )
