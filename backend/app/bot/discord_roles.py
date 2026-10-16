from __future__ import annotations

import re

import discord

from app.services.ranks import (
    AGENT_ROLES,
    VALORANT_RANKS,
    extract_min_rank_from_text,
    format_rank,
    normalize_rank_name,
    rank_meets_minimum,
    rank_tier,
)

__all__ = [
    "AGENT_ROLES",
    "VALORANT_RANKS",
    "extract_agents_from_member",
    "extract_from_member",
    "extract_valorant_rank_from_member",
    "extract_min_rank_from_roles",
    "extract_min_rank_from_text",
    "extract_rank_bounds_from_roles",
    "extract_wanted_agents_from_roles",
    "format_rank",
    "normalize_rank_name",
    "rank_meets_minimum",
    "rank_tier",
    "agents_labels_for_guild",
    "member_tags_line",
    "member_tags_line_plain",
    "rank_label_for_guild",
]


def _role_label_key(name: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", name).strip().lower()
    return " ".join(cleaned.split())


def extract_agents_from_member(member: discord.Member) -> list[str]:
    found = [role.name for role in member.roles if role.name in AGENT_ROLES]
    return sorted(found)


def extract_from_member(member: discord.Member) -> tuple[str | None, str | None]:
    best_rank: str | None = None
    best_tier = -1
    agents = extract_agents_from_member(member)
    agent_role = agents[0] if agents else None

    for role in member.roles:
        name = role.name.strip()
        normalized = normalize_rank_name(name)
        if normalized:
            tier = rank_tier(normalized)
            if tier > best_tier:
                best_tier = tier
                best_rank = normalized
        elif _role_label_key(name) in {_role_label_key(a) for a in AGENT_ROLES}:
            for agent in AGENT_ROLES:
                if agent.lower() in _role_label_key(name):
                    agent_role = agent
                    break

    return best_rank, agent_role


def extract_valorant_rank_from_member(
    member: discord.Member,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str | None:
    """Rank do membro via mapeamento admin (valorant_rank → role Discord), senão por nome da role."""
    if role_mappings:
        member_ids = {role.id for role in member.roles}
        best_rank: str | None = None
        best_tier = -1
        for (kind, rank_name), role_id in role_mappings.items():
            if kind != "valorant_rank" or role_id not in member_ids:
                continue
            normalized = normalize_rank_name(rank_name)
            if normalized is None:
                continue
            tier = rank_tier(normalized)
            if tier > best_tier:
                best_tier = tier
                best_rank = normalized
        if best_rank is not None:
            return best_rank
    rank, _agent = extract_from_member(member)
    return rank


def extract_min_rank_from_roles(roles: list[discord.Role]) -> str | None:
    min_rank, _max_rank = extract_rank_bounds_from_roles(roles)
    return min_rank


def extract_rank_bounds_from_roles(roles: list[discord.Role]) -> tuple[str | None, str | None]:
    found: list[str] = []
    for role in roles:
        normalized = normalize_rank_name(role.name)
        if normalized is not None:
            found.append(normalized)
    if not found:
        return None, None
    found.sort(key=rank_tier)
    if len(found) == 1:
        return found[0], None
    return found[0], found[-1]


def extract_wanted_agents_from_roles(roles: list[discord.Role]) -> list[str]:
    wanted: list[str] = []
    for role in roles:
        if role.name in AGENT_ROLES:
            wanted.append(role.name)
            continue
        key = _role_label_key(role.name)
        for agent in AGENT_ROLES:
            if agent.lower() in key and agent not in wanted:
                wanted.append(agent)
    return wanted


def rank_role_media(
    guild: discord.Guild | None,
    rank: str | None,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> tuple[str | None, str | None]:
    """URL do ícone da role de rank e emoji unicode da role (se existir)."""
    if guild is None or not rank:
        return None, None
    role = find_rank_role(guild, rank, role_mappings=role_mappings)
    if role is None:
        return None, None
    icon_url: str | None = None
    if role.icon is not None:
        icon_url = role.icon.url
    return icon_url, role.unicode_emoji


def _guild_role_by_id(guild: discord.Guild, role_id: int) -> discord.Role | None:
    get_role = getattr(guild, "get_role", None)
    if callable(get_role):
        mapped = get_role(role_id)
        if mapped is not None:
            return mapped
    for role in getattr(guild, "roles", ()) or ():
        if getattr(role, "id", None) == role_id:
            return role
    return None


def find_rank_role(
    guild: discord.Guild,
    rank: str,
    *,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> discord.Role | None:
    target = normalize_rank_name(rank)
    if target is None:
        return None
    if role_mappings:
        mapped_id = role_mappings.get(("valorant_rank", target))
        if mapped_id is not None:
            mapped = _guild_role_by_id(guild, mapped_id)
            if mapped is not None:
                return mapped
    target_lower = target.lower()
    for role in guild.roles:
        if normalize_rank_name(role.name) == target:
            return role
    for role in guild.roles:
        key = _role_label_key(role.name)
        if target_lower == key or target_lower in key.split():
            return role
    return None


def find_agent_role(
    guild: discord.Guild,
    agent: str,
    *,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> discord.Role | None:
    if agent not in AGENT_ROLES:
        return None
    if role_mappings:
        mapped_id = role_mappings.get(("agent_role", agent))
        if mapped_id is not None:
            mapped = guild.get_role(mapped_id)
            if mapped is not None:
                return mapped
    for role in guild.roles:
        if role.name == agent:
            return role
    agent_lower = agent.lower()
    for role in guild.roles:
        if agent_lower in _role_label_key(role.name):
            return role
    return None


def rank_label_for_guild(
    guild: discord.Guild | None,
    rank: str | None,
    mention_ids: list[int],
    *,
    with_role_emoji: bool = True,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str | None:
    if not rank:
        return None
    label: str | None = None
    emoji: str | None = None
    if guild is not None:
        role = find_rank_role(guild, rank, role_mappings=role_mappings)
        if role is not None:
            mention_ids.append(role.id)
            label = role.mention
            emoji = role.unicode_emoji
    if label is None:
        label = format_rank(rank)
    if with_role_emoji and emoji:
        return f"{emoji} {label}"
    return label


def agent_label_for_guild(
    guild: discord.Guild | None,
    agent: str | None,
    mention_ids: list[int],
    *,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str | None:
    if not agent:
        return None
    if guild is not None:
        role = find_agent_role(guild, agent, role_mappings=role_mappings)
        if role is not None:
            mention_ids.append(role.id)
            return role.mention
    return agent


def agents_labels_for_guild(
    guild: discord.Guild | None,
    agents: list[str],
    mention_ids: list[int],
    *,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str:
    labels: list[str] = []
    for agent in agents:
        label = agent_label_for_guild(guild, agent, mention_ids, role_mappings=role_mappings)
        if label:
            labels.append(label)
    return " · ".join(labels)


def member_tags_line_plain(
    guild: discord.Guild | None,
    member: discord.Member | None,
    stored_rank: str | None,
) -> str:
    """Rank/agente ao lado do host: texto + emoji, sem @role (convive com <@user> na embed)."""
    rank = stored_rank
    agents: list[str] = []
    if member is not None:
        live_rank, _single = extract_from_member(member)
        if live_rank:
            rank = live_rank
        agents = extract_agents_from_member(member)

    tags: list[str] = []
    if rank:
        _icon, emoji = rank_role_media(guild, rank)
        label = format_rank(rank)
        if emoji:
            tags.append(f"{emoji} {label}")
        elif label and label != "Sem rank":
            tags.append(label)
    if agents:
        tags.append(" · ".join(agents))
    elif member is not None:
        _, fallback_agent = extract_from_member(member)
        if fallback_agent:
            tags.append(fallback_agent)
    return " · ".join(tags)


def member_tags_line(
    guild: discord.Guild | None,
    member: discord.Member | None,
    stored_rank: str | None,
    mention_ids: list[int],
    *,
    role_mappings: dict[tuple[str, str], int] | None = None,
) -> str:
    rank = stored_rank
    agents: list[str] = []
    if member is not None:
        live_rank, _single = extract_from_member(member)
        if live_rank:
            rank = live_rank
        agents = extract_agents_from_member(member)

    tags: list[str] = []
    rank_label = rank_label_for_guild(guild, rank, mention_ids, role_mappings=role_mappings)
    if rank_label and rank_label != "Sem rank":
        tags.append(rank_label)
    if agents:
        tags.append(
            agents_labels_for_guild(guild, agents, mention_ids, role_mappings=role_mappings)
        )
    elif member is not None:
        _, fallback_agent = extract_from_member(member)
        agent_label = agent_label_for_guild(
            guild, fallback_agent, mention_ids, role_mappings=role_mappings
        )
        if agent_label:
            tags.append(agent_label)
    return " · ".join(tags)
