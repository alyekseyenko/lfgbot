from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import discord

from app.services.ranks import VALORANT_RANKS, normalize_rank_name

if TYPE_CHECKING:
    from app.db.models import Lobby
    from app.services.guild_config import GuildRuntimeConfig

LFG_EMBED_COLOR_SOURCES: frozenset[str] = frozenset({"mode", "host_rank", "min_rank", "max_rank"})

_HEX_COLOR = re.compile(r"^#?([0-9A-Fa-f]{6})$")

DEFAULT_RANK_EMBED_COLORS: dict[str, str] = {
    "Unranked": "4A4E5A",
    "Iron": "514F4A",
    "Bronze": "A0715C",
    "Silver": "BBC2C9",
    "Gold": "ECA82E",
    "Platinum": "59C9BB",
    "Diamond": "B489FF",
    "Ascendant": "1FA86A",
    "Immortal": "B23B4B",
    "Radiant": "F4E19D",
}

DEFAULT_IMMUNE_EMBED_COLOR = "FFD700"
DEFAULT_IMMUNE_EMBED_LABEL = "Pedido em destaque"
MAX_IMMUNE_EMBED_TIERS = 5
DEFAULT_COMPETITIVE_COLOR = "FF4655"
DEFAULT_UNRATED_COLOR = "5E98D9"
DEFAULT_FULL_COLOR = "C23B22"
DEFAULT_INACTIVE_COLOR = "4A4E5A"
DEFAULT_FOOTER_BRAND = "LFG Valorant"

LFG_EMBED_TEXT_LIMITS: dict[str, int] = {
    "panel_title": 256,
    "panel_description": 4096,
    "panel_lead": 512,
    "panel_cta": 512,
    "lobby_cta_open": 1024,
    "lobby_inactive_lead": 512,
    "lobby_empty_players": 1024,
    "lobby_private_code_hint": 1024,
    "author_prefix": 32,
    "footer_suffix": 128,
    "field_slots": 256,
    "field_expires": 256,
    "field_code_visibility": 256,
    "field_ranks": 256,
    "field_agents": 256,
    "field_players": 256,
    "field_party_code": 256,
    "lobby_simple_hint": 512,
}

SIMPLE_EMBED_TEXT_KEYS: frozenset[str] = frozenset(
    {
        "lobby_inactive_lead",
        "lobby_simple_hint",
        "author_prefix",
        "footer_suffix",
        "field_slots",
        "field_expires",
        "field_ranks",
        "field_party_code",
    }
)

DEFAULT_PANEL_LEAD = "**Procura team?**"
DEFAULT_PANEL_CTA = ""
DEFAULT_LOBBY_CTA_OPEN = "👇 **Usa os botões abaixo** para entrar ou sair."
DEFAULT_LOBBY_INACTIVE_LEAD = "**Este grupo já não está ativo.**"
DEFAULT_LOBBY_EMPTY_PLAYERS = "_Ninguém na lista — **Entrar** para te juntares._"
DEFAULT_LOBBY_PRIVATE_CODE_HINT = "_Oculto — carrega em **Entrar** para receber o código._"
DEFAULT_AUTHOR_PREFIX = "Host"
DEFAULT_FOOTER_SUFFIX = "· Expira à hora indicada (Lisboa)"


@dataclass(frozen=True, slots=True)
class ImmuneEmbedTier:
    label: str
    color: str
    role_ids: tuple[int, ...] = ()


def _int_list_from_json(raw: Any) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def normalize_immune_embed_tiers(raw: Any) -> tuple[ImmuneEmbedTier, ...]:
    if not isinstance(raw, list):
        return ()
    tiers: list[ImmuneEmbedTier] = []
    for item in raw[:MAX_IMMUNE_EMBED_TIERS]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or DEFAULT_IMMUNE_EMBED_LABEL).strip()[:64]
        if not label:
            label = DEFAULT_IMMUNE_EMBED_LABEL
        color = parse_embed_hex_color(
            item.get("color") if isinstance(item.get("color"), str) else None,
            default=DEFAULT_IMMUNE_EMBED_COLOR,
        )
        role_ids = tuple(_int_list_from_json(item.get("role_ids")))
        if not role_ids:
            continue
        tiers.append(ImmuneEmbedTier(label=label, color=color, role_ids=role_ids))
    return tuple(tiers)


def union_immune_role_ids_from_tiers(tiers: tuple[ImmuneEmbedTier, ...]) -> tuple[int, ...]:
    seen: set[int] = set()
    ordered: list[int] = []
    for tier in tiers:
        for role_id in tier.role_ids:
            if role_id not in seen:
                seen.add(role_id)
                ordered.append(role_id)
    return tuple(ordered)


def immune_embed_tiers_for_config(
    tiers_raw: Any,
    *,
    legacy_role_ids: tuple[int, ...],
    legacy_label: str,
    legacy_color: str,
) -> tuple[ImmuneEmbedTier, ...]:
    tiers = normalize_immune_embed_tiers(tiers_raw)
    if tiers:
        return tiers
    if legacy_role_ids:
        label = (legacy_label or DEFAULT_IMMUNE_EMBED_LABEL).strip()[
            :64
        ] or DEFAULT_IMMUNE_EMBED_LABEL
        color = parse_embed_hex_color(legacy_color, default=DEFAULT_IMMUNE_EMBED_COLOR)
        return (ImmuneEmbedTier(label=label, color=color, role_ids=legacy_role_ids),)
    return ()


@dataclass(frozen=True, slots=True)
class LobbyEmbedStyle:
    color_source: str = "mode"
    rank_embed_colors: dict[str, str] = field(default_factory=dict)
    competitive_color: str = DEFAULT_COMPETITIVE_COLOR
    unrated_color: str = DEFAULT_UNRATED_COLOR
    full_color: str = DEFAULT_FULL_COLOR
    inactive_color: str = DEFAULT_INACTIVE_COLOR
    decorative: bool = True
    footer_brand: str = DEFAULT_FOOTER_BRAND
    banner_url: str | None = None
    custom_texts: dict[str, str] = field(default_factory=dict)
    show_author: bool = True
    show_timestamp: bool = True
    show_rank_thumbnail: bool = True
    banner_on_panel: bool = True
    banner_on_lobby: bool = True
    panel_thumbnail_url: str | None = None
    panel_color: str = DEFAULT_COMPETITIVE_COLOR
    panel_footer_brand: str | None = None
    panel_banner_url: str | None = None
    panel_decorative: bool = True
    lobby_thumbnail_url: str | None = None
    immune_role_ids: tuple[int, ...] = ()
    immune_embed_enabled: bool = True
    immune_embed_color: str = DEFAULT_IMMUNE_EMBED_COLOR
    immune_embed_label: str = DEFAULT_IMMUNE_EMBED_LABEL
    immune_embed_tiers: tuple[ImmuneEmbedTier, ...] = ()

    def __post_init__(self) -> None:
        if self.color_source not in LFG_EMBED_COLOR_SOURCES:
            object.__setattr__(self, "color_source", "mode")
        label = (self.immune_embed_label or DEFAULT_IMMUNE_EMBED_LABEL).strip()
        if not label:
            label = DEFAULT_IMMUNE_EMBED_LABEL
        object.__setattr__(self, "immune_embed_label", label[:64])


def normalize_lfg_embed_custom_texts(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, limit in LFG_EMBED_TEXT_LIMITS.items():
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        out[key] = cleaned[:limit]
    return out


def embed_custom_text(style: LobbyEmbedStyle | None, key: str, default: str) -> str:
    if style is None:
        return default
    custom = style.custom_texts.get(key, "").strip()
    return custom if custom else default


@dataclass(frozen=True, slots=True)
class LfgEmbedSimpleSettings:
    color_source: str = "min_rank"
    competitive_color: str = DEFAULT_COMPETITIVE_COLOR
    unrated_color: str = DEFAULT_UNRATED_COLOR
    inactive_color: str = DEFAULT_INACTIVE_COLOR
    decorative: bool = False
    footer_brand: str | None = None
    custom_texts: dict[str, str] = field(default_factory=dict)
    show_author: bool = False
    show_timestamp: bool = False
    show_rank_thumbnail: bool = True
    lobby_thumbnail_url: str | None = None


def normalize_lfg_embed_simple_custom_texts(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in SIMPLE_EMBED_TEXT_KEYS:
        limit = LFG_EMBED_TEXT_LIMITS.get(key, 256)
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        out[key] = cleaned[:limit]
    return out


def normalize_lfg_embed_simple(raw: Any, *, fallback_footer_brand: str) -> LfgEmbedSimpleSettings:
    data = raw if isinstance(raw, dict) else {}
    color_source = data.get("color_source", "min_rank")
    if color_source not in LFG_EMBED_COLOR_SOURCES:
        color_source = "min_rank"
    footer_raw = data.get("footer_brand")
    footer_brand: str | None
    if isinstance(footer_raw, str) and footer_raw.strip():
        footer_brand = footer_raw.strip()[:64]
    else:
        footer_brand = None
    thumb_raw = data.get("lobby_thumbnail_url")
    thumb = thumb_raw.strip()[:2048] if isinstance(thumb_raw, str) and thumb_raw.strip() else None
    texts_raw = data.get("custom_texts", data.get("lfg_embed_custom_texts"))
    custom_texts = normalize_lfg_embed_simple_custom_texts(texts_raw)
    return LfgEmbedSimpleSettings(
        color_source=color_source,
        competitive_color=parse_embed_hex_color(
            data.get("competitive_color"), default=DEFAULT_COMPETITIVE_COLOR
        ),
        unrated_color=parse_embed_hex_color(
            data.get("unrated_color"), default=DEFAULT_UNRATED_COLOR
        ),
        inactive_color=parse_embed_hex_color(
            data.get("inactive_color"), default=DEFAULT_INACTIVE_COLOR
        ),
        decorative=bool(data.get("decorative", False)),
        footer_brand=footer_brand,
        custom_texts=custom_texts,
        show_author=bool(data.get("show_author", False)),
        show_timestamp=bool(data.get("show_timestamp", False)),
        show_rank_thumbnail=bool(data.get("show_rank_thumbnail", True)),
        lobby_thumbnail_url=thumb,
    )


def lfg_embed_simple_to_storage(settings: LfgEmbedSimpleSettings) -> dict[str, object]:
    out: dict[str, object] = {
        "color_source": settings.color_source,
        "competitive_color": settings.competitive_color,
        "unrated_color": settings.unrated_color,
        "inactive_color": settings.inactive_color,
        "decorative": settings.decorative,
        "show_author": settings.show_author,
        "show_timestamp": settings.show_timestamp,
        "show_rank_thumbnail": settings.show_rank_thumbnail,
        "custom_texts": dict(settings.custom_texts),
    }
    if settings.footer_brand:
        out["footer_brand"] = settings.footer_brand
    if settings.lobby_thumbnail_url:
        out["lobby_thumbnail_url"] = settings.lobby_thumbnail_url
    return out


def simple_lobby_embed_style_from_config(config: GuildRuntimeConfig) -> LobbyEmbedStyle:
    simple = config.lfg_embed_simple
    brand = (simple.footer_brand or config.lfg_embed_footer_brand or DEFAULT_FOOTER_BRAND).strip()[
        :64
    ]
    return LobbyEmbedStyle(
        color_source=simple.color_source,
        rank_embed_colors=dict(config.rank_embed_colors),
        competitive_color=parse_embed_hex_color(
            simple.competitive_color, default=DEFAULT_COMPETITIVE_COLOR
        ),
        unrated_color=parse_embed_hex_color(simple.unrated_color, default=DEFAULT_UNRATED_COLOR),
        full_color=parse_embed_hex_color(config.lfg_embed_full_color, default=DEFAULT_FULL_COLOR),
        inactive_color=parse_embed_hex_color(simple.inactive_color, default=DEFAULT_INACTIVE_COLOR),
        decorative=simple.decorative,
        footer_brand=brand or DEFAULT_FOOTER_BRAND,
        banner_url=None,
        custom_texts=dict(simple.custom_texts),
        show_author=simple.show_author,
        show_timestamp=simple.show_timestamp,
        show_rank_thumbnail=simple.show_rank_thumbnail,
        banner_on_panel=config.lfg_embed_banner_on_panel,
        banner_on_lobby=False,
        panel_thumbnail_url=(config.lfg_panel_thumbnail_url or "").strip() or None,
        panel_color=parse_embed_hex_color(
            config.lfg_panel_color, default=DEFAULT_COMPETITIVE_COLOR
        ),
        panel_footer_brand=(config.lfg_panel_footer_brand or "").strip()[:64] or None,
        panel_banner_url=(config.lfg_panel_banner_url or "").strip() or None,
        panel_decorative=bool(config.lfg_panel_decorative),
        lobby_thumbnail_url=(simple.lobby_thumbnail_url or "").strip() or None,
        immune_role_ids=config.immune_role_ids,
        immune_embed_enabled=bool(config.immune_embed_enabled),
        immune_embed_color=config.immune_embed_color,
        immune_embed_label=config.immune_embed_label,
        immune_embed_tiers=config.immune_embed_tiers,
    )


def lobby_embed_style_for_post(
    config: GuildRuntimeConfig, post_style: str | None
) -> LobbyEmbedStyle:
    from app.services.lobby_post_style import is_simple_post_style

    if is_simple_post_style(post_style):
        return simple_lobby_embed_style_from_config(config)
    return lobby_embed_style_from_config(config)


def lobby_embed_style_from_config(config: GuildRuntimeConfig) -> LobbyEmbedStyle:
    banner = (config.lfg_embed_banner_url or "").strip() or None
    brand = (config.lfg_embed_footer_brand or DEFAULT_FOOTER_BRAND).strip()[:64]
    return LobbyEmbedStyle(
        color_source=config.lfg_embed_color_source,
        rank_embed_colors=dict(config.rank_embed_colors),
        competitive_color=parse_embed_hex_color(
            config.lfg_embed_competitive_color, default=DEFAULT_COMPETITIVE_COLOR
        ),
        unrated_color=parse_embed_hex_color(
            config.lfg_embed_unrated_color, default=DEFAULT_UNRATED_COLOR
        ),
        full_color=parse_embed_hex_color(config.lfg_embed_full_color, default=DEFAULT_FULL_COLOR),
        inactive_color=parse_embed_hex_color(
            config.lfg_embed_inactive_color, default=DEFAULT_INACTIVE_COLOR
        ),
        decorative=config.lfg_embed_decorative,
        footer_brand=brand or DEFAULT_FOOTER_BRAND,
        banner_url=banner,
        custom_texts=dict(config.lfg_embed_custom_texts),
        show_author=config.lfg_embed_show_author,
        show_timestamp=config.lfg_embed_show_timestamp,
        show_rank_thumbnail=config.lfg_embed_show_thumbnail,
        banner_on_panel=config.lfg_embed_banner_on_panel,
        banner_on_lobby=config.lfg_embed_banner_on_lobby,
        panel_thumbnail_url=(config.lfg_panel_thumbnail_url or "").strip() or None,
        panel_color=parse_embed_hex_color(
            config.lfg_panel_color, default=DEFAULT_COMPETITIVE_COLOR
        ),
        panel_footer_brand=(config.lfg_panel_footer_brand or "").strip()[:64] or None,
        panel_banner_url=(config.lfg_panel_banner_url or "").strip() or None,
        panel_decorative=bool(config.lfg_panel_decorative),
        lobby_thumbnail_url=(config.lfg_embed_thumbnail_url or "").strip() or None,
        immune_role_ids=config.immune_role_ids,
        immune_embed_enabled=config.immune_embed_enabled,
        immune_embed_color=config.immune_embed_color,
        immune_embed_label=config.immune_embed_label,
        immune_embed_tiers=config.immune_embed_tiers,
    )


def mode_colour_for_lobby(mode: str, style: LobbyEmbedStyle | None) -> discord.Colour:
    if style is not None:
        if mode.lower() == "unrated":
            return discord_colour_from_hex(
                parse_embed_hex_color(style.unrated_color, default=DEFAULT_UNRATED_COLOR)
            )
        return discord_colour_from_hex(
            parse_embed_hex_color(style.competitive_color, default=DEFAULT_COMPETITIVE_COLOR)
        )
    if mode.lower() == "unrated":
        return discord_colour_from_hex(DEFAULT_UNRATED_COLOR)
    return discord_colour_from_hex(DEFAULT_COMPETITIVE_COLOR)


def state_colours_from_style(
    style: LobbyEmbedStyle | None,
) -> tuple[discord.Colour, discord.Colour]:
    if style is None:
        return (
            discord_colour_from_hex(DEFAULT_FULL_COLOR),
            discord_colour_from_hex(DEFAULT_INACTIVE_COLOR),
        )
    return (
        discord_colour_from_hex(
            parse_embed_hex_color(style.full_color, default=DEFAULT_FULL_COLOR)
        ),
        discord_colour_from_hex(
            parse_embed_hex_color(style.inactive_color, default=DEFAULT_INACTIVE_COLOR)
        ),
    )


def parse_embed_hex_color(raw: str | None, *, default: str) -> str:
    if not raw:
        return default.upper()
    match = _HEX_COLOR.match(raw.strip())
    if not match:
        return default.upper()
    return match.group(1).upper()


def normalize_rank_embed_colors(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        rank = normalize_rank_name(str(key))
        if rank is None or rank not in VALORANT_RANKS:
            continue
        if not isinstance(value, str):
            continue
        hex_value = parse_embed_hex_color(value, default="")
        if hex_value:
            out[rank] = hex_value
    return out


def discord_colour_from_hex(hex6: str) -> discord.Colour:
    return discord.Colour(int(hex6, 16))


def rank_embed_colour(
    rank: str | None,
    custom_colors: dict[str, str],
) -> discord.Colour | None:
    if not rank:
        return None
    normalized = normalize_rank_name(rank) or rank
    hex_value = custom_colors.get(normalized) or DEFAULT_RANK_EMBED_COLORS.get(normalized)
    if not hex_value:
        return None
    return discord_colour_from_hex(hex_value)


def member_has_immune_role(member: discord.Member | None, immune_role_ids: tuple[int, ...]) -> bool:
    return find_host_immune_role(member, immune_role_ids) is not None


def find_host_immune_role(
    member: discord.Member | None,
    immune_role_ids: tuple[int, ...],
) -> discord.Role | None:
    if member is None or not immune_role_ids:
        return None
    immune = set(immune_role_ids)
    matches = [role for role in member.roles if role.id in immune]
    if not matches:
        return None
    return max(matches, key=lambda role: role.position)


@dataclass(frozen=True, slots=True)
class ImmuneHighlightContext:
    role_id: int
    role_name: str
    role_colour: discord.Colour
    role_icon_url: str | None
    label: str

    @property
    def role_mention(self) -> str:
        return f"<@&{self.role_id}>"


def _highlight_from_role(
    role: discord.Role,
    *,
    label: str,
    fallback_colour_hex: str,
) -> ImmuneHighlightContext:
    colour = role.colour
    if colour is None or colour.value == 0:
        colour = discord_colour_from_hex(
            parse_embed_hex_color(fallback_colour_hex, default=DEFAULT_IMMUNE_EMBED_COLOR)
        )
    icon_url: str | None = None
    if role.icon is not None:
        icon_url = role.icon.url
    return ImmuneHighlightContext(
        role_id=role.id,
        role_name=role.name,
        role_colour=colour,
        role_icon_url=icon_url,
        label=label,
    )


def immune_highlight_from_member(
    member: discord.Member | None,
    immune_role_ids: tuple[int, ...],
    *,
    label: str,
    fallback_colour_hex: str,
) -> ImmuneHighlightContext | None:
    role = find_host_immune_role(member, immune_role_ids)
    if role is None:
        return None
    return _highlight_from_role(role, label=label, fallback_colour_hex=fallback_colour_hex)


def immune_highlight_from_tiers(
    member: discord.Member | None,
    tiers: tuple[ImmuneEmbedTier, ...],
) -> ImmuneHighlightContext | None:
    """Prioridade 1 = primeiro nível da lista (maior destaque)."""
    if member is None or not tiers:
        return None
    for tier in tiers:
        role = find_host_immune_role(member, tier.role_ids)
        if role is None:
            continue
        return _highlight_from_role(role, label=tier.label, fallback_colour_hex=tier.color)
    return None


def rank_for_color_source(lobby: Lobby, source: str) -> str | None:
    if source == "host_rank":
        return lobby.host.rank
    if source == "min_rank":
        return lobby.min_rank
    if source == "max_rank":
        return lobby.max_rank
    return None


def resolve_lobby_embed_colour(
    lobby: Lobby,
    guild: discord.Guild | None,
    style: LobbyEmbedStyle | None,
    *,
    mode_colour: discord.Colour,
    full_colour: discord.Colour,
    inactive_colour: discord.Colour,
    host_member: discord.Member | None = None,
) -> tuple[discord.Colour, ImmuneHighlightContext | None]:
    """Cor da barra + destaque se o host tiver role isenta configurada."""
    from app.db.models import LobbyState

    if lobby.state in (LobbyState.expired, LobbyState.closed):
        return inactive_colour, None
    if lobby.state == LobbyState.full:
        return full_colour, None

    if style is None:
        return mode_colour, None

    if host_member is None and guild is not None:
        host_member = guild.get_member(lobby.host.discord_id)
    if style.immune_embed_enabled:
        tiers = style.immune_embed_tiers
        if not tiers and style.immune_role_ids:
            tiers = (
                ImmuneEmbedTier(
                    label=style.immune_embed_label,
                    color=style.immune_embed_color,
                    role_ids=style.immune_role_ids,
                ),
            )
        highlight = immune_highlight_from_tiers(host_member, tiers)
        if highlight is not None:
            return highlight.role_colour, highlight

    if style.color_source != "mode":
        rank = rank_for_color_source(lobby, style.color_source)
        rank_colour = rank_embed_colour(rank, style.rank_embed_colors)
        if rank_colour is not None:
            return rank_colour, None

    return mode_colour, None
