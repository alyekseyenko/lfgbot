from dataclasses import dataclass
from zoneinfo import ZoneInfo

import discord

from app.bot.discord_roles import (
    agents_labels_for_guild,
    member_tags_line,
    rank_label_for_guild,
    rank_role_media,
)
from app.services.agents import parse_wanted_agents_csv
from app.db.models import Lobby, LobbyMember, LobbyState, User

PORTUGAL = ZoneInfo("Europe/Lisbon")

# Inspirado na paleta Valorant (vermelho competitivo, azul unrated).
COLOUR_COMPETITIVE = discord.Colour(0xFF4655)
COLOUR_UNRATED = discord.Colour(0x5E98D9)
COLOUR_FULL = discord.Colour(0xC23B22)
COLOUR_INACTIVE = discord.Colour(0x4A4E5A)


@dataclass(frozen=True, slots=True)
class LobbyEmbedBuild:
    embed: discord.Embed
    mention_role_ids: list[int]


def _active_members(lobby: Lobby) -> list[LobbyMember]:
    return [m for m in lobby.members if m.left_at is None]


def _mode_colour(mode: str) -> discord.Colour:
    if mode.lower() == "unrated":
        return COLOUR_UNRATED
    return COLOUR_COMPETITIVE


def _state_colour(lobby: Lobby) -> discord.Colour:
    if lobby.state in (LobbyState.expired, LobbyState.closed):
        return COLOUR_INACTIVE
    if lobby.state == LobbyState.full:
        return COLOUR_FULL
    return _mode_colour(lobby.mode)


def _status_label(state: LobbyState) -> str:
    return {
        LobbyState.open: "Aberto",
        LobbyState.full: "Cheio",
        LobbyState.closed: "Fechado",
        LobbyState.expired: "Expirado",
    }[state]


def _lobby_is_inactive(lobby: Lobby) -> bool:
    return lobby.state in (LobbyState.closed, LobbyState.expired)


def _strike_main_text(text: str, inactive: bool) -> str:
    if not inactive or not text.strip():
        return text
    return f"~~{text}~~"


def _slots_meter(joined: int, total_slots: int) -> str:
    if total_slots <= 0:
        return "`—`"
    filled = min(joined, total_slots)
    free = max(0, total_slots - joined)
    bar = "▰" * filled + "▱" * free
    return f"`{bar}` **{free}** vaga(s) · **{joined}** na lista"


def _player_line(
    guild: discord.Guild | None,
    user: User,
    mention_ids: list[int],
) -> str:
    member = guild.get_member(user.discord_id) if guild is not None else None
    tags = member_tags_line(guild, member, user.rank, mention_ids)
    if tags:
        return f"• **{user.name}** — {tags}"
    return f"• **{user.name}**"


def build_lobby_embed(
    lobby: Lobby,
    guild: discord.Guild | None = None,
    *,
    thumbnail_url: str | None = None,
) -> LobbyEmbedBuild:
    mention_ids: list[int] = []
    members = _active_members(lobby)
    joined = len(members)
    free = max(0, lobby.slots - joined)
    colour = _state_colour(lobby)
    status = _status_label(lobby.state)
    inactive = _lobby_is_inactive(lobby)

    title = _strike_main_text(f"{lobby.mode} · {status}", inactive)
    host_member = guild.get_member(lobby.host.discord_id) if guild is not None else None
    host_tags = member_tags_line(guild, host_member, lobby.host.rank, mention_ids)
    host_line = f"**{lobby.host.name}**"
    if host_tags:
        host_line = f"{host_line} — {host_tags}"
    host_line = _strike_main_text(host_line, inactive)

    expires_local = lobby.expires_at.astimezone(PORTUGAL)
    visibility = "Público" if lobby.party_code_public else "Privado"

    description = host_line
    if inactive:
        description = f"**Este grupo já não está ativo.**\n{host_line}"

    embed = discord.Embed(
        title=title,
        colour=colour,
        timestamp=lobby.expires_at,
    )
    embed.set_author(
        name=_strike_main_text(f"Host · {lobby.host.name}", inactive),
        icon_url=host_member.display_avatar.url if host_member else None,
    )

    embed.description = description

    embed.add_field(
        name="Vagas",
        value=_strike_main_text(_slots_meter(joined, lobby.slots), inactive),
        inline=True,
    )
    embed.add_field(
        name="Expira",
        value=_strike_main_text(
            f"**{expires_local.strftime('%H:%M')}** Lisboa",
            inactive,
        ),
        inline=True,
    )
    embed.add_field(
        name="Código",
        value=_strike_main_text(f"**{visibility}**", inactive),
        inline=True,
    )

    if lobby.min_rank or lobby.max_rank:
        if lobby.min_rank and lobby.max_rank:
            min_label = rank_label_for_guild(guild, lobby.min_rank, mention_ids)
            max_label = rank_label_for_guild(guild, lobby.max_rank, mention_ids)
            rank_value = f"{min_label or lobby.min_rank} → {max_label or lobby.max_rank}"
        elif lobby.min_rank:
            min_label = rank_label_for_guild(guild, lobby.min_rank, mention_ids)
            rank_value = f"mín. {min_label or lobby.min_rank}"
        else:
            max_label = rank_label_for_guild(guild, lobby.max_rank, mention_ids)
            rank_value = f"máx. {max_label or lobby.max_rank}"
        rank_mode = "verificados" if lobby.ranks_verified else "informativos"
        embed.add_field(
            name=f"Ranks ({rank_mode})",
            value=_strike_main_text(rank_value, inactive),
            inline=False,
        )

    min_icon, _min_emoji = rank_role_media(guild, lobby.min_rank)
    max_icon, _max_emoji = rank_role_media(guild, lobby.max_rank)
    footer_icon: str | None = None
    if lobby.min_rank and lobby.max_rank and min_icon and max_icon:
        embed.set_thumbnail(url=min_icon)
        footer_icon = max_icon
    elif lobby.min_rank and min_icon:
        embed.set_thumbnail(url=min_icon)
    elif lobby.max_rank and max_icon:
        embed.set_thumbnail(url=max_icon)
    elif thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    wanted_agents = parse_wanted_agents_csv(lobby.wanted_agents)
    if wanted_agents:
        agent_value = agents_labels_for_guild(guild, wanted_agents, mention_ids)
        embed.add_field(
            name="Roles procurados",
            value=_strike_main_text(agent_value or ", ".join(wanted_agents), inactive),
            inline=False,
        )

    if lobby.party_code and lobby.party_code_public:
        code_display = (
            _strike_main_text(lobby.party_code, inactive)
            if inactive
            else f"```{lobby.party_code}```"
        )
        embed.add_field(
            name="Código da party",
            value=code_display,
            inline=False,
        )
    elif lobby.party_code and not lobby.party_code_public and lobby.state in (
        LobbyState.open,
        LobbyState.full,
    ):
        embed.add_field(
            name="Código da party",
            value="_Oculto — carrega em **Entrar** para receber o código._",
            inline=False,
        )

    if members:
        lines = [_player_line(guild, m.user, mention_ids) for m in members]
        players_value = _strike_main_text("\n".join(lines), inactive)
        embed.add_field(name="Jogadores", value=players_value, inline=False)
    elif inactive:
        embed.add_field(
            name="Jogadores",
            value=_strike_main_text("_Lista final do grupo._", True),
            inline=False,
        )
    else:
        embed.add_field(
            name="Jogadores",
            value="_Ninguém na lista — **Entrar** para te juntares._",
            inline=False,
        )

    short_id = str(lobby.id).split("-")[0]
    footer_text = f"LFG · {short_id} · Expira à hora indicada (fuso Lisboa)"
    embed.set_footer(text=footer_text, icon_url=footer_icon)

    unique_ids = list(dict.fromkeys(mention_ids))
    return LobbyEmbedBuild(embed=embed, mention_role_ids=unique_ids)


def lobby_view_enabled(lobby: Lobby) -> bool:
    return lobby.state in (LobbyState.open, LobbyState.full)


def allowed_mentions_for_roles(role_ids: list[int]) -> discord.AllowedMentions:
    roles = [discord.Object(id=rid) for rid in role_ids]
    return discord.AllowedMentions(everyone=False, users=False, roles=roles, replied_user=False)
