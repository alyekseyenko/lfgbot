from dataclasses import dataclass
from zoneinfo import ZoneInfo

import discord

from app.bot.discord_roles import (
    agents_labels_for_guild,
    extract_valorant_rank_from_member,
    member_tags_line,
    rank_label_for_guild,
    rank_role_media,
)
from app.db.models import Lobby, LobbyMember, LobbyState, User
from app.services.agents import parse_wanted_agents_csv
from app.services.lobby_post_style import is_simple_post_style
from app.services.lfg_embed_style import (
    DEFAULT_AUTHOR_PREFIX,
    DEFAULT_FOOTER_SUFFIX,
    DEFAULT_LOBBY_CTA_OPEN,
    DEFAULT_LOBBY_EMPTY_PLAYERS,
    DEFAULT_LOBBY_INACTIVE_LEAD,
    DEFAULT_LOBBY_PRIVATE_CODE_HINT,
    ImmuneHighlightContext,
    LobbyEmbedStyle,
    embed_custom_text,
    mode_colour_for_lobby,
    resolve_lobby_embed_colour,
    state_colours_from_style,
)

PORTUGAL = ZoneInfo("Europe/Lisbon")
DEFAULT_LOBBY_SIMPLE_HINT = "Junta-te no jogo com o código — sem lista nesta mensagem."
DEFAULT_HOST_NO_RANK_FOOTER = "Jogador sem rank verificado"


@dataclass(frozen=True, slots=True)
class _HostFooterAccent:
    icon_url: str | None
    note: str | None


def _host_footer_accent(
    guild: discord.Guild | None,
    host_member: discord.Member | None,
    immune_highlight: ImmuneHighlightContext | None,
    *,
    role_mappings: dict[tuple[str, str], int] | None,
    inactive: bool,
) -> _HostFooterAccent:
    """Rodapé: ícone da role isenta ou rank do host (mapeamento admin → role Discord)."""
    if inactive:
        return _HostFooterAccent(None, None)
    if immune_highlight is not None:
        return _HostFooterAccent(immune_highlight.role_icon_url, None)
    if host_member is None:
        return _HostFooterAccent(None, DEFAULT_HOST_NO_RANK_FOOTER)
    live_rank = extract_valorant_rank_from_member(host_member, role_mappings=role_mappings)
    if live_rank is None:
        return _HostFooterAccent(None, DEFAULT_HOST_NO_RANK_FOOTER)
    icon_url, _emoji = rank_role_media(guild, live_rank, role_mappings=role_mappings)
    return _HostFooterAccent(icon_url, None)


def _host_display_label(
    host_member: discord.Member | None,
    host_user: User,
) -> str:
    """Nome visível no embed (menções <@id> no embed não resolvem em servidores grandes)."""
    if host_member is not None:
        return f"**{host_member.display_name}**"
    name = (host_user.name or "").strip()
    if name:
        return f"**{name}**"
    return f"<@{host_user.discord_id}>"


def _footer_text_and_icon(
    footer_text: str,
    accent: _HostFooterAccent,
) -> tuple[str, str | None]:
    if accent.note:
        footer_text = f"{footer_text} · {accent.note}"
    return footer_text, accent.icon_url

# Fallbacks quando não há estilo de guild (ex. testes).
COLOUR_COMPETITIVE = discord.Colour(0xFF4655)
COLOUR_UNRATED = discord.Colour(0x5E98D9)
COLOUR_FULL = discord.Colour(0xC23B22)
COLOUR_INACTIVE = discord.Colour(0x4A4E5A)


@dataclass(frozen=True, slots=True)
class LobbyEmbedBuild:
    embed: discord.Embed
    mention_role_ids: list[int]
    mention_user_ids: list[int]


def _active_members(lobby: Lobby) -> list[LobbyMember]:
    return [m for m in lobby.members if m.left_at is None]


def _mode_colour(mode: str, style: LobbyEmbedStyle | None) -> discord.Colour:
    return mode_colour_for_lobby(mode, style)


def _status_label(state: LobbyState, decorative: bool) -> str:
    labels = {
        LobbyState.open: ("Aberto", "ABERTO"),
        LobbyState.full: ("Cheio", "CHEIO"),
        LobbyState.closed: ("Fechado", "FECHADO"),
        LobbyState.expired: ("Expirado", "EXPIRADO"),
    }
    short, loud = labels[state]
    return loud if decorative else short


def _lobby_is_inactive(lobby: Lobby) -> bool:
    return lobby.state in (LobbyState.closed, LobbyState.expired)


def _strike_main_text(text: str, inactive: bool) -> str:
    if not inactive or not text.strip():
        return text
    return f"~~{text}~~"


def _slots_meter(joined: int, total_slots: int, decorative: bool) -> str:
    if total_slots <= 0:
        return "`—`"
    filled = min(joined, total_slots)
    free = max(0, total_slots - joined)
    if decorative:
        bar = "🟥" * filled + "⬛" * free
    else:
        bar = "▰" * filled + "▱" * free
    return f"{bar}\n**{free}** vaga(s) · **{joined}** na lista"


def _mode_title_prefix(mode: str, decorative: bool) -> str:
    if not decorative:
        return mode
    if mode.lower() == "unrated":
        return f"🎮 {mode.upper()}"
    return f"⚔️ {mode.upper()}"


def _field_label(name: str, decorative: bool, emoji: str) -> str:
    return f"{emoji} {name}" if decorative else name


def _embed_field_label(
    embed_style: LobbyEmbedStyle | None,
    key: str,
    default_name: str,
    decorative: bool,
    emoji: str,
) -> str:
    custom = embed_custom_text(embed_style, key, "")
    if custom:
        return custom
    return _field_label(default_name, decorative, emoji)


def _player_line(
    guild: discord.Guild | None,
    user: User,
    mention_ids: list[int],
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str:
    member = guild.get_member(user.discord_id) if guild is not None else None
    tags = member_tags_line(guild, member, user.rank, mention_ids, role_mappings=role_mappings)
    if tags:
        return f"• **{user.name}** — {tags}"
    return f"• **{user.name}**"


def _rank_range_display(
    lobby: Lobby,
    guild: discord.Guild | None,
    mention_ids: list[int],
    role_mappings: dict[tuple[str, str], int] | None,
) -> str:
    if lobby.min_rank and lobby.max_rank:
        min_label = rank_label_for_guild(
            guild, lobby.min_rank, mention_ids, role_mappings=role_mappings
        )
        max_label = rank_label_for_guild(
            guild, lobby.max_rank, mention_ids, role_mappings=role_mappings
        )
        return f"{min_label or lobby.min_rank} → {max_label or lobby.max_rank}"
    if lobby.min_rank:
        min_label = rank_label_for_guild(
            guild, lobby.min_rank, mention_ids, role_mappings=role_mappings
        )
        return f"mín. {min_label or lobby.min_rank}"
    if lobby.max_rank:
        max_label = rank_label_for_guild(
            guild, lobby.max_rank, mention_ids, role_mappings=role_mappings
        )
        return f"máx. {max_label or lobby.max_rank}"
    return "Qualquer"


def _build_simple_lobby_embed(
    lobby: Lobby,
    guild: discord.Guild | None = None,
    *,
    thumbnail_url: str | None = None,
    role_mappings: dict[tuple[str, str], int] | None = None,
    embed_style: LobbyEmbedStyle | None = None,
    host_member: discord.Member | None = None,
) -> LobbyEmbedBuild:
    mention_ids: list[int] = []
    decorative = embed_style.decorative if embed_style is not None else False
    inactive = _lobby_is_inactive(lobby)
    mode_colour = _mode_colour(lobby.mode, embed_style)
    full_colour, inactive_colour = state_colours_from_style(embed_style)
    if host_member is None and guild is not None:
        host_member = guild.get_member(lobby.host.discord_id)

    colour, immune_highlight = resolve_lobby_embed_colour(
        lobby,
        guild,
        embed_style,
        mode_colour=mode_colour,
        full_colour=full_colour,
        inactive_colour=inactive_colour,
        host_member=host_member,
    )
    expires_local = lobby.expires_at.astimezone(PORTUGAL)
    if immune_highlight is not None and not inactive:
        banner = immune_highlight.label.strip() or immune_highlight.role_name
        title = _strike_main_text(
            f"⭐ {banner.upper()}" if decorative else banner,
            inactive,
        )
    else:
        title = _strike_main_text(
            _mode_title_prefix(lobby.mode, decorative),
            inactive,
        )
    host_label = _host_display_label(host_member, lobby.host)
    description = _strike_main_text(host_label, inactive)
    if inactive:
        inactive_lead = embed_custom_text(
            embed_style, "lobby_inactive_lead", DEFAULT_LOBBY_INACTIVE_LEAD
        )
        description = f"{inactive_lead}\n{host_label}"
    else:
        hint = embed_custom_text(
            embed_style, "lobby_simple_hint", DEFAULT_LOBBY_SIMPLE_HINT
        ).strip()
        if hint:
            description = f"{description}\n_{hint}_"

    show_timestamp = embed_style is not None and embed_style.show_timestamp
    embed = discord.Embed(
        title=title,
        colour=colour,
        timestamp=lobby.expires_at if show_timestamp else None,
    )
    if embed_style is not None and embed_style.show_author:
        prefix = embed_custom_text(embed_style, "author_prefix", DEFAULT_AUTHOR_PREFIX)
        author_name = (
            host_member.display_name if host_member is not None else lobby.host.name
        )
        embed.set_author(
            name=_strike_main_text(f"{prefix} · {author_name}", inactive),
            icon_url=host_member.display_avatar.url if host_member is not None else None,
        )
    embed.description = description

    if lobby.party_code:
        code_display = (
            _strike_main_text(lobby.party_code, inactive)
            if inactive
            else f"```\n{lobby.party_code}\n```"
        )
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_party_code", "Código", decorative, "🔑"
            ),
            value=code_display,
            inline=False,
        )

    embed.add_field(
        name=_embed_field_label(embed_style, "field_slots", "Vagas", decorative, "🎯"),
        value=_strike_main_text(f"**{lobby.slots}**", inactive),
        inline=True,
    )
    rank_value = _rank_range_display(lobby, guild, mention_ids, role_mappings)
    embed.add_field(
        name=_embed_field_label(embed_style, "field_ranks", "Rank", decorative, "🏅"),
        value=_strike_main_text(rank_value, inactive),
        inline=True,
    )
    embed.add_field(
        name=_embed_field_label(embed_style, "field_expires", "Expira", decorative, "⏱"),
        value=_strike_main_text(
            f"**{expires_local.strftime('%H:%M')}** Lisboa",
            inactive,
        ),
        inline=True,
    )

    show_thumb = embed_style is None or embed_style.show_rank_thumbnail
    fallback_thumb = (
        (embed_style.lobby_thumbnail_url if embed_style is not None else None) or thumbnail_url
    )
    if immune_highlight is not None and immune_highlight.role_icon_url and not inactive:
        embed.set_thumbnail(url=immune_highlight.role_icon_url)
    elif show_thumb:
        min_icon, _ = rank_role_media(guild, lobby.min_rank, role_mappings=role_mappings)
        max_icon, _ = rank_role_media(guild, lobby.max_rank, role_mappings=role_mappings)
        if lobby.min_rank and min_icon:
            embed.set_thumbnail(url=min_icon)
        elif lobby.max_rank and max_icon:
            embed.set_thumbnail(url=max_icon)
        elif fallback_thumb:
            embed.set_thumbnail(url=fallback_thumb)

    short_id = str(lobby.id).split("-")[0]
    brand = (
        embed_style.footer_brand.strip()
        if embed_style is not None and embed_style.footer_brand.strip()
        else "LFG Valorant"
    )
    expires_line = f"Expira {expires_local.strftime('%H:%M')} Lisboa"
    if inactive:
        footer_text = f"{brand} · #{short_id} · Pedido encerrado"
    else:
        footer_text = f"{brand} · #{short_id} · {expires_line} · Fecha com o botão Fechar"
    accent = _host_footer_accent(
        guild,
        host_member,
        immune_highlight,
        role_mappings=role_mappings,
        inactive=inactive,
    )
    footer_text, footer_icon = _footer_text_and_icon(footer_text, accent)
    embed.set_footer(text=footer_text, icon_url=footer_icon)

    unique_role_ids = list(dict.fromkeys(mention_ids))
    return LobbyEmbedBuild(
        embed=embed,
        mention_role_ids=unique_role_ids,
        mention_user_ids=[],
    )


def build_lobby_embed(
    lobby: Lobby,
    guild: discord.Guild | None = None,
    *,
    thumbnail_url: str | None = None,
    role_mappings: dict[tuple[str, str], int] | None = None,
    embed_style: LobbyEmbedStyle | None = None,
    host_member: discord.Member | None = None,
) -> LobbyEmbedBuild:
    if is_simple_post_style(getattr(lobby, "post_style", None)):
        return _build_simple_lobby_embed(
            lobby,
            guild,
            thumbnail_url=thumbnail_url,
            role_mappings=role_mappings,
            embed_style=embed_style,
            host_member=host_member,
        )
    mention_ids: list[int] = []
    simple_post = False
    members = _active_members(lobby)
    joined = len(members) if not simple_post else 0
    decorative = embed_style.decorative if embed_style is not None else True
    mode_colour = _mode_colour(lobby.mode, embed_style)
    full_colour, inactive_colour = state_colours_from_style(embed_style)
    if host_member is None and guild is not None:
        host_member = guild.get_member(lobby.host.discord_id)

    colour, immune_highlight = resolve_lobby_embed_colour(
        lobby,
        guild,
        embed_style,
        mode_colour=mode_colour,
        full_colour=full_colour,
        inactive_colour=inactive_colour,
        host_member=host_member,
    )
    status = _status_label(lobby.state, decorative)
    inactive = _lobby_is_inactive(lobby)

    host_label = _host_display_label(host_member, lobby.host)
    host_tags = member_tags_line(
        guild,
        host_member,
        lobby.host.rank,
        mention_ids,
        role_mappings=role_mappings,
    )
    host_line = host_label
    if host_tags:
        host_line = f"{host_label} — {host_tags}"
    host_line = _strike_main_text(host_line, inactive)

    expires_local = lobby.expires_at.astimezone(PORTUGAL)
    visibility = "Público" if lobby.party_code_public else "Privado"

    if immune_highlight is not None and not inactive:
        banner = immune_highlight.label.strip() or immune_highlight.role_name
        title = _strike_main_text(f"⭐ {banner.upper()}" if decorative else banner, inactive)
        mode_line = _strike_main_text(
            f"{_mode_title_prefix(lobby.mode, decorative)} · {status}",
            inactive,
        )
        description = f"{mode_line}\n{host_line}"
    else:
        title = _strike_main_text(
            f"{_mode_title_prefix(lobby.mode, decorative)} · {status}",
            inactive,
        )
        description = host_line

    inactive_lead = embed_custom_text(
        embed_style, "lobby_inactive_lead", DEFAULT_LOBBY_INACTIVE_LEAD
    )
    if inactive:
        description = f"{inactive_lead}\n{host_line}"
    elif lobby.state == LobbyState.open and decorative and not simple_post:
        cta = embed_custom_text(embed_style, "lobby_cta_open", DEFAULT_LOBBY_CTA_OPEN)
        description = f"{description}\n\n{cta}"

    show_timestamp = embed_style is None or embed_style.show_timestamp
    embed = discord.Embed(
        title=title,
        colour=colour,
        timestamp=lobby.expires_at if show_timestamp else None,
    )
    show_author = embed_style is None or embed_style.show_author
    if show_author:
        prefix = embed_custom_text(embed_style, "author_prefix", DEFAULT_AUTHOR_PREFIX)
        author_name = f"{prefix} · {host_member.display_name if host_member is not None else lobby.host.name}"
        author_icon = host_member.display_avatar.url if host_member is not None else None
        embed.set_author(
            name=_strike_main_text(author_name, inactive),
            icon_url=author_icon,
        )

    if simple_post and not inactive:
        simple_hint = embed_custom_text(
            embed_style, "lobby_simple_hint", DEFAULT_LOBBY_SIMPLE_HINT
        )
        description = f"{description}\n\n_{simple_hint}_"
    embed.description = description

    if simple_post:
        slots_value = f"**{lobby.slots}** vagas"
    else:
        slots_value = _slots_meter(joined, lobby.slots, decorative)
    embed.add_field(
        name=_embed_field_label(embed_style, "field_slots", "Vagas", decorative, "🎯"),
        value=_strike_main_text(slots_value, inactive),
        inline=True,
    )
    embed.add_field(
        name=_embed_field_label(embed_style, "field_expires", "Expira", decorative, "⏱"),
        value=_strike_main_text(
            f"**{expires_local.strftime('%H:%M')}** Lisboa",
            inactive,
        ),
        inline=True,
    )
    if not simple_post:
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_code_visibility", "Código", decorative, "🔒"
            ),
            value=_strike_main_text(f"**{visibility}**", inactive),
            inline=True,
        )

    if lobby.min_rank or lobby.max_rank:
        if lobby.min_rank and lobby.max_rank:
            min_label = rank_label_for_guild(
                guild, lobby.min_rank, mention_ids, role_mappings=role_mappings
            )
            max_label = rank_label_for_guild(
                guild, lobby.max_rank, mention_ids, role_mappings=role_mappings
            )
            rank_value = f"{min_label or lobby.min_rank} → {max_label or lobby.max_rank}"
        elif lobby.min_rank:
            min_label = rank_label_for_guild(
                guild, lobby.min_rank, mention_ids, role_mappings=role_mappings
            )
            rank_value = f"mín. {min_label or lobby.min_rank}"
        else:
            max_label = rank_label_for_guild(
                guild, lobby.max_rank, mention_ids, role_mappings=role_mappings
            )
            rank_value = f"máx. {max_label or lobby.max_rank}"
        if simple_post:
            rank_field_default = "Rank"
        else:
            rank_mode = "verificados" if lobby.ranks_verified else "informativos"
            rank_field_default = f"Ranks ({rank_mode})"
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_ranks", rank_field_default, decorative, "🏅"
            ),
            value=_strike_main_text(rank_value, inactive),
            inline=False,
        )
    elif simple_post and not inactive:
        embed.add_field(
            name=_embed_field_label(embed_style, "field_ranks", "Rank", decorative, "🏅"),
            value=_strike_main_text("Qualquer", inactive),
            inline=False,
        )

    show_thumb = embed_style is None or embed_style.show_rank_thumbnail
    fallback_thumb = (
        (embed_style.lobby_thumbnail_url if embed_style is not None else None) or thumbnail_url
    )
    if immune_highlight is not None and immune_highlight.role_icon_url and not inactive:
        embed.set_thumbnail(url=immune_highlight.role_icon_url)
    elif show_thumb:
        min_icon, _min_emoji = rank_role_media(guild, lobby.min_rank, role_mappings=role_mappings)
        max_icon, _max_emoji = rank_role_media(guild, lobby.max_rank, role_mappings=role_mappings)
        if lobby.min_rank and lobby.max_rank and min_icon and max_icon:
            embed.set_thumbnail(url=min_icon)
        elif lobby.min_rank and min_icon:
            embed.set_thumbnail(url=min_icon)
        elif lobby.max_rank and max_icon:
            embed.set_thumbnail(url=max_icon)
        elif fallback_thumb:
            embed.set_thumbnail(url=fallback_thumb)

    wanted_agents = parse_wanted_agents_csv(lobby.wanted_agents)
    if wanted_agents and not simple_post:
        agent_value = agents_labels_for_guild(
            guild, wanted_agents, mention_ids, role_mappings=role_mappings
        )
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_agents", "Roles procurados", decorative, "🎭"
            ),
            value=_strike_main_text(agent_value or ", ".join(wanted_agents), inactive),
            inline=False,
        )

    if lobby.party_code and (lobby.party_code_public or simple_post):
        code_display = (
            _strike_main_text(lobby.party_code, inactive)
            if inactive
            else f"```\n{lobby.party_code}\n```"
        )
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_party_code", "Código da party", decorative, "🔑"
            ),
            value=code_display,
            inline=False,
        )
    elif (
        lobby.party_code
        and not lobby.party_code_public
        and lobby.state
        in (
            LobbyState.open,
            LobbyState.full,
        )
    ):
        private_hint = embed_custom_text(
            embed_style, "lobby_private_code_hint", DEFAULT_LOBBY_PRIVATE_CODE_HINT
        )
        embed.add_field(
            name=_embed_field_label(
                embed_style, "field_party_code", "Código da party", decorative, "🔑"
            ),
            value=private_hint,
            inline=False,
        )

    if not simple_post:
        if members:
            lines = [
                _player_line(guild, m.user, mention_ids, role_mappings=role_mappings)
                for m in members
            ]
            players_value = _strike_main_text("\n".join(lines), inactive)
            embed.add_field(
                name=_embed_field_label(
                    embed_style, "field_players", "Jogadores", decorative, "👥"
                ),
                value=players_value,
                inline=False,
            )
        elif inactive:
            embed.add_field(
                name=_embed_field_label(
                    embed_style, "field_players", "Jogadores", decorative, "👥"
                ),
                value=_strike_main_text("_Lista final do grupo._", True),
                inline=False,
            )
        else:
            empty_players = embed_custom_text(
                embed_style, "lobby_empty_players", DEFAULT_LOBBY_EMPTY_PLAYERS
            )
            embed.add_field(
                name=_embed_field_label(
                    embed_style, "field_players", "Jogadores", decorative, "👥"
                ),
                value=empty_players,
                inline=False,
            )

    short_id = str(lobby.id).split("-")[0]
    brand = (
        embed_style.footer_brand.strip()
        if embed_style is not None and embed_style.footer_brand.strip()
        else "LFG Valorant"
    )
    suffix = embed_custom_text(embed_style, "footer_suffix", DEFAULT_FOOTER_SUFFIX)
    footer_text = f"{brand} · #{short_id} {suffix}".strip()
    accent = _host_footer_accent(
        guild,
        host_member,
        immune_highlight,
        role_mappings=role_mappings,
        inactive=inactive,
    )
    footer_text, footer_icon = _footer_text_and_icon(footer_text, accent)
    embed.set_footer(text=footer_text, icon_url=footer_icon)

    banner_on = embed_style is None or embed_style.banner_on_lobby
    if (
        embed_style is not None
        and embed_style.banner_url
        and banner_on
        and not inactive
        and lobby.state in (LobbyState.open, LobbyState.full)
    ):
        embed.set_image(url=embed_style.banner_url)

    unique_role_ids = list(dict.fromkeys(mention_ids))
    return LobbyEmbedBuild(
        embed=embed,
        mention_role_ids=unique_role_ids,
        mention_user_ids=[],
    )


def lobby_view_enabled(lobby: Lobby) -> bool:
    return lobby.state in (LobbyState.open, LobbyState.full)


def allowed_mentions_for_roles(
    role_ids: list[int],
    *,
    user_ids: list[int] | None = None,
) -> discord.AllowedMentions:
    """Só menções listadas notificam; utilizadores/roles têm de estar explícitos."""
    roles = [discord.Object(id=rid) for rid in role_ids]
    users = [discord.Object(id=uid) for uid in dict.fromkeys(user_ids or ())]
    return discord.AllowedMentions(everyone=False, users=users, roles=roles, replied_user=False)


def allowed_mentions_for_lobby(built: LobbyEmbedBuild) -> discord.AllowedMentions:
    return allowed_mentions_for_roles(
        built.mention_role_ids,
        user_ids=built.mention_user_ids,
    )
