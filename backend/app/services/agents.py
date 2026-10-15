from __future__ import annotations

from app.services.ranks import AGENT_ROLES


def parse_wanted_agents_csv(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    found: list[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name in AGENT_ROLES and name not in found:
            found.append(name)
    return found


def serialize_wanted_agents(agents: list[str]) -> str | None:
    cleaned = [a for a in agents if a in AGENT_ROLES]
    if not cleaned:
        return None
    return ",".join(cleaned)


def applicant_matches_wanted(
    wanted: list[str], applicant_agents: frozenset[str] | set[str]
) -> bool:
    if not wanted:
        return True
    return bool(applicant_agents.intersection(wanted))
