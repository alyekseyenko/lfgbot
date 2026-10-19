from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: str
    username: str
    avatar: str | None = None


class GuildOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    bot_installed: bool


class ImmuneEmbedTierOut(BaseModel):
    label: str = "Pedido em destaque"
    color: str = "FFD700"
    role_ids: list[str] = Field(default_factory=list)


class GuildSettingsOut(BaseModel):
    lfg_channel_ids: list[str] = Field(default_factory=list)
    announce_channel_id: str | None = None
    weekly_leaderboard_anchor: str | None = None
    reputation_channel_id: str = "0"
    reputation_delay_minutes: int = Field(default=50, ge=10, le=180)
    reputation_negative_threshold: int = Field(default=-15, ge=-10_000, le=-1)
    reputation_negative_role_id: str = "0"
    reputation_positive_threshold: int = Field(default=25, ge=1, le=10_000)
    reputation_positive_role_id: str = "0"
    auto_format_messages: bool = True
    default_lfg_mode: str = "Competitivo"
    gamification_enabled: bool = False
    stats_channel_id: str = "0"
    log_channel_id: str = "0"
    panel_sticky_enabled: bool = True
    lobby_ttl_minutes: int = 45
    party_code_max_length: int = Field(default=6, ge=4, le=12)
    immune_role_ids: list[str] = Field(default_factory=list)
    lfg_embed_color_source: Literal["mode", "host_rank", "min_rank", "max_rank"] = "mode"
    rank_embed_colors: dict[str, str] = Field(default_factory=dict)
    lfg_embed_competitive_color: str = "FF4655"
    lfg_embed_unrated_color: str = "5E98D9"
    lfg_embed_full_color: str = "C23B22"
    lfg_embed_inactive_color: str = "4A4E5A"
    lfg_embed_decorative: bool = True
    lfg_embed_footer_brand: str = "LFG Valorant"
    lfg_embed_banner_url: str | None = None
    lfg_embed_custom_texts: dict[str, str] = Field(default_factory=dict)
    lfg_embed_show_author: bool = True
    lfg_embed_show_timestamp: bool = True
    lfg_embed_show_thumbnail: bool = True
    lfg_embed_banner_on_panel: bool = True
    lfg_embed_banner_on_lobby: bool = True
    lfg_panel_thumbnail_url: str | None = None
    lfg_panel_color: str = "FF4655"
    lfg_panel_footer_brand: str | None = None
    lfg_panel_banner_url: str | None = None
    lfg_panel_decorative: bool = True
    lfg_embed_thumbnail_url: str | None = None
    lfg_embed_simple: dict[str, object] = Field(default_factory=dict)
    lfg_embed_detailed: dict[str, object] = Field(default_factory=dict)
    lfg_embed_panel: dict[str, object] = Field(default_factory=dict)
    lfg_post_style_simple_enabled: bool = True
    lfg_post_style_detailed_enabled: bool = True
    immune_embed_enabled: bool = True
    immune_embed_color: str = "FFD700"
    immune_embed_label: str = "Pedido em destaque"
    immune_embed_tiers: list[ImmuneEmbedTierOut] = Field(default_factory=list)
    search_penalty_enabled: bool = True
    search_penalty_early_minutes: int = Field(default=5, ge=1, le=1440)
    search_penalty_early_max_count: int = Field(default=3, ge=1, le=20)
    search_penalty_mid_minutes: int = Field(default=15, ge=1, le=1440)
    search_penalty_severe_hours: int = Field(default=12, ge=1, le=168)
    host_recreate_cooldown_seconds: int = Field(default=300, ge=0, le=86400)
    immune_host_recreate_cooldown_seconds: int = Field(default=10, ge=0, le=86400)
    guide_channel_id: str = "0"
    guide_body: str | None = None
    stats_legacy_lobbies_created: int = Field(default=0, ge=0)
    stats_legacy_joins: int = Field(default=0, ge=0)
    stats_legacy_users: int = Field(default=0, ge=0)


class GuildSettingsPatch(BaseModel):
    lfg_channel_ids: list[str] | None = None
    announce_channel_id: str | None = None
    weekly_leaderboard_anchor: str | None = None
    reputation_channel_id: str | None = None
    reputation_delay_minutes: int | None = Field(default=None, ge=10, le=180)
    reputation_negative_threshold: int | None = Field(default=None, ge=-10_000, le=-1)
    reputation_negative_role_id: str | None = None
    reputation_positive_threshold: int | None = Field(default=None, ge=1, le=10_000)
    reputation_positive_role_id: str | None = None
    auto_format_messages: bool | None = None
    default_lfg_mode: str | None = None
    gamification_enabled: bool | None = None
    stats_channel_id: str | None = None
    log_channel_id: str | None = None
    panel_sticky_enabled: bool | None = None
    lobby_ttl_minutes: int | None = None
    party_code_max_length: int | None = Field(default=None, ge=4, le=12)
    immune_role_ids: list[str] | None = None
    lfg_embed_color_source: Literal["mode", "host_rank", "min_rank", "max_rank"] | None = None
    rank_embed_colors: dict[str, str] | None = None
    lfg_embed_competitive_color: str | None = None
    lfg_embed_unrated_color: str | None = None
    lfg_embed_full_color: str | None = None
    lfg_embed_inactive_color: str | None = None
    lfg_embed_decorative: bool | None = None
    lfg_embed_footer_brand: str | None = None
    lfg_embed_banner_url: str | None = None
    lfg_embed_custom_texts: dict[str, str] | None = None
    lfg_embed_show_author: bool | None = None
    lfg_embed_show_timestamp: bool | None = None
    lfg_embed_show_thumbnail: bool | None = None
    lfg_embed_banner_on_panel: bool | None = None
    lfg_embed_banner_on_lobby: bool | None = None
    lfg_panel_thumbnail_url: str | None = None
    lfg_panel_color: str | None = None
    lfg_panel_footer_brand: str | None = None
    lfg_panel_banner_url: str | None = None
    lfg_panel_decorative: bool | None = None
    lfg_embed_thumbnail_url: str | None = None
    lfg_embed_simple: dict[str, object] | None = None
    lfg_embed_detailed: dict[str, object] | None = None
    lfg_embed_panel: dict[str, object] | None = None
    lfg_post_style_simple_enabled: bool | None = None
    lfg_post_style_detailed_enabled: bool | None = None
    immune_embed_enabled: bool | None = None
    immune_embed_color: str | None = None
    immune_embed_label: str | None = None
    immune_embed_tiers: list[ImmuneEmbedTierOut] | None = None
    search_penalty_enabled: bool | None = None
    search_penalty_early_minutes: int | None = Field(default=None, ge=1, le=1440)
    search_penalty_early_max_count: int | None = Field(default=None, ge=1, le=20)
    search_penalty_mid_minutes: int | None = Field(default=None, ge=1, le=1440)
    search_penalty_severe_hours: int | None = Field(default=None, ge=1, le=168)
    host_recreate_cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    immune_host_recreate_cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    guide_channel_id: str | None = None
    guide_body: str | None = None
    stats_legacy_lobbies_created: int | None = Field(default=None, ge=0)
    stats_legacy_joins: int | None = Field(default=None, ge=0)
    stats_legacy_users: int | None = Field(default=None, ge=0)


class DiscordRoleOut(BaseModel):
    id: str
    name: str
    color: int
    position: int


class DiscordChannelOut(BaseModel):
    id: str
    name: str
    type: int


class RoleMappingItem(BaseModel):
    mapping_type: str
    logical_key: str
    discord_role_id: str


class RoleMappingsPut(BaseModel):
    mappings: list[RoleMappingItem]


class LobbiesBySourceOut(BaseModel):
    slash: int = 0
    panel: int = 0
    chat: int = 0
    unknown: int = 0


class GuildStatsOut(BaseModel):
    active_lobbies: int
    lobbies_created_period: int
    joins_period: int
    active_users_7d: int = 0
    groups_filled_period: int = 0
    groups_completed_period: int = 0
    avg_minutes_to_fill: float = 0.0
    avg_minutes_to_end: float = 0.0
    created_by_source: LobbiesBySourceOut = Field(default_factory=LobbiesBySourceOut)
    period_days: int = 30
    lobbies_created_lifetime: int = 0
    joins_lifetime: int = 0
    users_lifetime: int = 0
    lobbies_created_bot: int = 0
    joins_bot: int = 0
    users_bot: int = 0
    stats_legacy_lobbies_created: int = 0
    stats_legacy_joins: int = 0
    stats_legacy_users: int = 0


class InviteUrlOut(BaseModel):
    url: str


class AbilityOut(BaseModel):
    slot: str = ""
    display_name: str = ""
    display_icon: str | None = None


class ValorantAgentOut(BaseModel):
    uuid: str
    display_name: str
    role_name: str
    display_icon_url: str | None = None
    full_portrait_url: str | None = None
    abilities: list[AbilityOut] = Field(default_factory=list)


class ValorantRankOut(BaseModel):
    tier: int
    display_name: str
    small_icon_url: str | None = None


class ValorantPlayerCardOut(BaseModel):
    uuid: str
    display_name: str
    small_art_url: str | None = None
    wide_art_url: str | None = None
    large_art_url: str | None = None


class CatalogMetaOut(BaseModel):
    last_synced_at: str | None = None


class CatalogSyncOut(BaseModel):
    agents: int
    ranks: int
    player_cards: int


class ValorantAgentRoleItem(BaseModel):
    agent_uuid: str
    discord_role_id: str


class ValorantAgentRolesPut(BaseModel):
    mappings: list[ValorantAgentRoleItem]


class ProfileStatsOut(BaseModel):
    level: str
    host_completions: int
    player_completions: int
    total_completions: int
    kicks_received: int
    next_level_hint: str
    rooms_created: int = 0
    next_min_rooms: int | None = None
    creator_level_number: int = 0


class CreatorLevelItem(BaseModel):
    level_number: int
    name: str
    min_rooms: int
    discord_role_id: str | None = None


class CreatorLevelsPut(BaseModel):
    levels: list[CreatorLevelItem]


class RecentCompletionOut(BaseModel):
    mode: str
    kind: str
    awarded_at: str


class ProfileAgentOut(BaseModel):
    uuid: str
    display_name: str
    role_name: str
    display_icon_url: str | None = None
    full_portrait_url: str | None = None
    abilities: list[AbilityOut] = Field(default_factory=list)


class PlayerProfileOut(BaseModel):
    discord_id: str
    name: str
    rank_label: str | None = None
    rank_icon_url: str | None = None
    riot_id: str | None = None
    stats: ProfileStatsOut
    recent: list[RecentCompletionOut] = Field(default_factory=list)
    agents: list[ProfileAgentOut] = Field(default_factory=list)
    player_card_uuid: str | None = None
    player_card_wide_url: str | None = None
    is_self: bool = False


class ProfilePatch(BaseModel):
    riot_id: str | None = None
    player_card_uuid: str | None = None
