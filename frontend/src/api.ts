import type { LfgEmbedSimpleSettings } from "./embedAdminConfig";

const jsonHeaders = { "Content-Type": "application/json" };

const COLOR_SOURCES = new Set(["mode", "host_rank", "min_rank", "max_rank"]);

function normalizeLfgEmbedSimple(raw: unknown): LfgEmbedSimpleSettings {
  const o =
    raw && typeof raw === "object" && !Array.isArray(raw)
      ? (raw as Record<string, unknown>)
      : {};
  const texts =
    o.custom_texts && typeof o.custom_texts === "object" && !Array.isArray(o.custom_texts)
      ? (o.custom_texts as Record<string, string>)
      : {};
  const colorSource = o.color_source;
  return {
    color_source:
      typeof colorSource === "string" && COLOR_SOURCES.has(colorSource)
        ? (colorSource as LfgEmbedSimpleSettings["color_source"])
        : undefined,
    competitive_color:
      typeof o.competitive_color === "string" ? o.competitive_color : undefined,
    unrated_color: typeof o.unrated_color === "string" ? o.unrated_color : undefined,
    inactive_color: typeof o.inactive_color === "string" ? o.inactive_color : undefined,
    decorative: typeof o.decorative === "boolean" ? o.decorative : undefined,
    footer_brand:
      typeof o.footer_brand === "string"
        ? o.footer_brand
        : o.footer_brand === null
          ? null
          : undefined,
    custom_texts: { ...texts },
    show_author: typeof o.show_author === "boolean" ? o.show_author : undefined,
    show_timestamp: typeof o.show_timestamp === "boolean" ? o.show_timestamp : undefined,
    show_rank_thumbnail:
      typeof o.show_rank_thumbnail === "boolean" ? o.show_rank_thumbnail : undefined,
    lobby_thumbnail_url:
      typeof o.lobby_thumbnail_url === "string"
        ? o.lobby_thumbnail_url
        : o.lobby_thumbnail_url === null
          ? null
          : undefined,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "include", ...init });
  if (!response.ok) {
    const text = await response.text();
    let message = text || `Erro ${response.status}`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      /* corpo não é JSON */
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** IDs Discord (snowflakes) como string — evita perda de precisão em JavaScript. */
export type Snowflake = string;

export type User = { id: Snowflake; username: string; avatar: string | null };
export type Guild = { id: Snowflake; name: string; icon: string | null; bot_installed: boolean };

export type ImmuneEmbedTier = {
  label: string;
  color: string;
  role_ids: Snowflake[];
};

export const MAX_IMMUNE_EMBED_TIERS = 5;

export type GuildSettings = {
  lfg_channel_ids: Snowflake[];
  announce_channel_id: Snowflake | null;
  auto_format_messages: boolean;
  default_lfg_mode: string;
  gamification_enabled: boolean;
  stats_channel_id: Snowflake;
  log_channel_id: Snowflake;
  panel_sticky_enabled: boolean;
  lobby_ttl_minutes: number;
  immune_role_ids: Snowflake[];
  lfg_embed_color_source: "mode" | "host_rank" | "min_rank" | "max_rank";
  rank_embed_colors: Record<string, string>;
  lfg_embed_competitive_color: string;
  lfg_embed_unrated_color: string;
  lfg_embed_full_color: string;
  lfg_embed_inactive_color: string;
  lfg_embed_decorative: boolean;
  lfg_embed_footer_brand: string;
  lfg_embed_banner_url: string | null;
  lfg_embed_custom_texts: Record<string, string>;
  lfg_embed_show_author: boolean;
  lfg_embed_show_timestamp: boolean;
  lfg_embed_show_thumbnail: boolean;
  lfg_embed_banner_on_panel: boolean;
  lfg_embed_banner_on_lobby: boolean;
  lfg_panel_thumbnail_url: string | null;
  lfg_panel_color: string;
  lfg_panel_footer_brand: string | null;
  lfg_panel_banner_url: string | null;
  lfg_panel_decorative: boolean;
  lfg_embed_thumbnail_url: string | null;
  lfg_embed_simple: LfgEmbedSimpleSettings;
  immune_embed_enabled: boolean;
  immune_embed_color: string;
  immune_embed_label: string;
  immune_embed_tiers: ImmuneEmbedTier[];
  search_penalty_enabled: boolean;
  search_penalty_early_minutes: number;
  search_penalty_early_max_count: number;
  search_penalty_mid_minutes: number;
  search_penalty_severe_hours: number;
  host_recreate_cooldown_seconds: number;
  immune_host_recreate_cooldown_seconds: number;
  guide_channel_id: Snowflake;
  guide_body: string | null;
  stats_legacy_lobbies_created: number;
  stats_legacy_joins: number;
  stats_legacy_users: number;
};
export type DiscordChannel = { id: Snowflake; name: string; type: number };
export type DiscordRole = { id: Snowflake; name: string; color: number; position: number };
export type RoleMapping = {
  mapping_type: string;
  logical_key: string;
  discord_role_id: Snowflake;
};
export type LobbiesBySource = {
  slash: number;
  panel: number;
  chat: number;
  unknown: number;
};

export type ValorantAgent = {
  uuid: string;
  display_name: string;
  role_name: string;
  display_icon_url: string | null;
  full_portrait_url: string | null;
  abilities: { slot: string; display_name: string; display_icon: string | null }[];
};

export type ValorantAgentRoleMapping = {
  agent_uuid: string;
  discord_role_id: Snowflake;
};

export type ValorantPlayerCard = {
  uuid: string;
  display_name: string;
  small_art_url: string | null;
  wide_art_url: string | null;
  large_art_url: string | null;
};

export type PlayerProfile = {
  discord_id: Snowflake;
  name: string;
  rank_label: string | null;
  rank_icon_url: string | null;
  riot_id: string | null;
  player_card_uuid: string | null;
  stats: {
    level: string;
    host_completions: number;
    player_completions: number;
    total_completions: number;
    kicks_received: number;
    next_level_hint: string;
  };
  recent: { mode: string; kind: string; awarded_at: string }[];
  agents: ValorantAgent[];
  player_card_wide_url: string | null;
  is_self: boolean;
};

export type GuildStats = {
  active_lobbies: number;
  lobbies_created_period: number;
  joins_period: number;
  active_users_7d: number;
  groups_filled_period: number;
  groups_completed_period: number;
  avg_minutes_to_fill: number;
  avg_minutes_to_end: number;
  created_by_source: LobbiesBySource;
  period_days: number;
  lobbies_created_lifetime: number;
  joins_lifetime: number;
  users_lifetime: number;
  lobbies_created_bot: number;
  joins_bot: number;
  users_bot: number;
  stats_legacy_lobbies_created: number;
  stats_legacy_joins: number;
  stats_legacy_users: number;
};

function normalizeImmuneEmbedTiers(s: Partial<GuildSettings>): ImmuneEmbedTier[] {
  if (s.immune_embed_tiers && s.immune_embed_tiers.length > 0) {
    return s.immune_embed_tiers.slice(0, MAX_IMMUNE_EMBED_TIERS).map((tier) => ({
      label: tier.label?.trim() || "Pedido em destaque",
      color: (tier.color ?? "FFD700").replace("#", "").toUpperCase().slice(0, 6),
      role_ids: tier.role_ids ?? [],
    }));
  }
  if (s.immune_role_ids && s.immune_role_ids.length > 0) {
    return [
      {
        label: s.immune_embed_label ?? "Pedido em destaque",
        color: (s.immune_embed_color ?? "FFD700").replace("#", "").toUpperCase(),
        role_ids: s.immune_role_ids,
      },
    ];
  }
  return [];
}

export function unionImmuneRoleIds(tiers: ImmuneEmbedTier[]): Snowflake[] {
  const seen = new Set<Snowflake>();
  const out: Snowflake[] = [];
  for (const tier of tiers) {
    for (const id of tier.role_ids) {
      if (!seen.has(id)) {
        seen.add(id);
        out.push(id);
      }
    }
  }
  return out;
}

/** Garante defaults quando a API devolve settings antigas ou parciais. */
export function normalizeGuildSettings(s: Partial<GuildSettings>): GuildSettings {
  const immune_embed_tiers = normalizeImmuneEmbedTiers(s);
  const immune_role_ids =
    s.immune_role_ids && s.immune_role_ids.length > 0
      ? s.immune_role_ids
      : unionImmuneRoleIds(immune_embed_tiers);
  return {
    lfg_channel_ids: s.lfg_channel_ids ?? [],
    announce_channel_id: s.announce_channel_id ?? null,
    auto_format_messages: s.auto_format_messages ?? true,
    default_lfg_mode: s.default_lfg_mode ?? "Competitivo",
    gamification_enabled: s.gamification_enabled ?? false,
    stats_channel_id: s.stats_channel_id ?? "0",
    log_channel_id: s.log_channel_id ?? "0",
    panel_sticky_enabled: s.panel_sticky_enabled ?? true,
    lobby_ttl_minutes: s.lobby_ttl_minutes ?? 45,
    immune_role_ids,
    lfg_embed_color_source: s.lfg_embed_color_source ?? "mode",
    rank_embed_colors: { ...(s.rank_embed_colors ?? {}) },
    lfg_embed_competitive_color: (s.lfg_embed_competitive_color ?? "FF4655")
      .replace("#", "")
      .toUpperCase()
      .slice(0, 6),
    lfg_embed_unrated_color: (s.lfg_embed_unrated_color ?? "5E98D9")
      .replace("#", "")
      .toUpperCase()
      .slice(0, 6),
    lfg_embed_full_color: (s.lfg_embed_full_color ?? "C23B22")
      .replace("#", "")
      .toUpperCase()
      .slice(0, 6),
    lfg_embed_inactive_color: (s.lfg_embed_inactive_color ?? "4A4E5A")
      .replace("#", "")
      .toUpperCase()
      .slice(0, 6),
    lfg_embed_decorative: s.lfg_embed_decorative ?? true,
    lfg_embed_footer_brand: (s.lfg_embed_footer_brand ?? "LFG Valorant").trim().slice(0, 64) || "LFG Valorant",
    lfg_embed_banner_url: (s.lfg_embed_banner_url ?? "").trim() || null,
    lfg_embed_custom_texts: { ...(s.lfg_embed_custom_texts ?? {}) },
    lfg_embed_show_author: s.lfg_embed_show_author ?? true,
    lfg_embed_show_timestamp: s.lfg_embed_show_timestamp ?? true,
    lfg_embed_show_thumbnail: s.lfg_embed_show_thumbnail ?? true,
    lfg_embed_banner_on_panel: s.lfg_embed_banner_on_panel ?? true,
    lfg_embed_banner_on_lobby: s.lfg_embed_banner_on_lobby ?? true,
    lfg_panel_thumbnail_url: (s.lfg_panel_thumbnail_url ?? "").trim() || null,
    lfg_panel_color: (s.lfg_panel_color ?? "FF4655").replace("#", "").toUpperCase().slice(0, 6),
    lfg_panel_footer_brand: (s.lfg_panel_footer_brand ?? "").trim().slice(0, 64) || null,
    lfg_panel_banner_url: (s.lfg_panel_banner_url ?? "").trim() || null,
    lfg_panel_decorative: s.lfg_panel_decorative ?? true,
    lfg_embed_thumbnail_url: (s.lfg_embed_thumbnail_url ?? "").trim() || null,
    lfg_embed_simple: normalizeLfgEmbedSimple(s.lfg_embed_simple),
    immune_embed_enabled: s.immune_embed_enabled ?? true,
    immune_embed_color: s.immune_embed_color ?? "FFD700",
    immune_embed_label: s.immune_embed_label ?? "Pedido em destaque",
    immune_embed_tiers,
    search_penalty_enabled: s.search_penalty_enabled ?? true,
    search_penalty_early_minutes: s.search_penalty_early_minutes ?? 5,
    search_penalty_early_max_count: s.search_penalty_early_max_count ?? 3,
    search_penalty_mid_minutes: s.search_penalty_mid_minutes ?? 15,
    search_penalty_severe_hours: s.search_penalty_severe_hours ?? 12,
    host_recreate_cooldown_seconds: s.host_recreate_cooldown_seconds ?? 300,
    immune_host_recreate_cooldown_seconds:
      s.immune_host_recreate_cooldown_seconds ?? 10,
    guide_channel_id: s.guide_channel_id ?? "0",
    guide_body: s.guide_body ?? null,
    stats_legacy_lobbies_created: s.stats_legacy_lobbies_created ?? 0,
    stats_legacy_joins: s.stats_legacy_joins ?? 0,
    stats_legacy_users: s.stats_legacy_users ?? 0,
  };
}

export const api = {
  me: () => request<User>("/auth/me"),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  guilds: () => request<Guild[]>("/guilds"),
  inviteUrl: () => request<{ url: string }>("/invite-url"),
  settings: (guildId: Snowflake) =>
    request<GuildSettings>(`/guilds/${guildId}/settings`).then(normalizeGuildSettings),
  patchSettings: (guildId: Snowflake, body: Partial<GuildSettings>) =>
    request<GuildSettings>(`/guilds/${guildId}/settings`, {
      method: "PATCH",
      headers: jsonHeaders,
      body: JSON.stringify(body),
    }).then(normalizeGuildSettings),
  channels: (guildId: Snowflake) =>
    request<DiscordChannel[]>(`/guilds/${guildId}/discord-channels`),
  roles: (guildId: Snowflake) => request<DiscordRole[]>(`/guilds/${guildId}/discord-roles`),
  roleMappings: (guildId: Snowflake) =>
    request<RoleMapping[]>(`/guilds/${guildId}/role-mappings`),
  putRoleMappings: (guildId: Snowflake, mappings: RoleMapping[]) =>
    request<RoleMapping[]>(`/guilds/${guildId}/role-mappings`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ mappings }),
    }),
  stats: (guildId: Snowflake) => request<GuildStats>(`/guilds/${guildId}/stats`),
  publishGuildGuide: (guildId: Snowflake) =>
    request<{ status: string }>(`/guilds/${guildId}/guide/publish`, { method: "POST" }),
  catalogMeta: () => request<{ last_synced_at: string | null }>("/catalog/meta"),
  catalogAgents: () => request<ValorantAgent[]>("/catalog/agents"),
  catalogPlayerCards: () => request<ValorantPlayerCard[]>("/catalog/player-cards"),
  syncCatalog: () =>
    request<{ agents: number; ranks: number; player_cards: number }>("/catalog/sync", {
      method: "POST",
    }),
  valorantAgentRoles: (guildId: Snowflake) =>
    request<ValorantAgentRoleMapping[]>(`/guilds/${guildId}/valorant-agent-roles`),
  putValorantAgentRoles: (guildId: Snowflake, mappings: ValorantAgentRoleMapping[]) =>
    request<ValorantAgentRoleMapping[]>(`/guilds/${guildId}/valorant-agent-roles`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify({ mappings }),
    }),
  myProfile: () => request<PlayerProfile>("/profiles/me"),
  patchMyProfile: (body: { riot_id?: string | null; player_card_uuid?: string | null }) =>
    request<PlayerProfile>("/profiles/me", {
      method: "PATCH",
      headers: jsonHeaders,
      body: JSON.stringify(body),
    }),
  profile: (discordId: Snowflake) => request<PlayerProfile>(`/profiles/${discordId}`),
};
