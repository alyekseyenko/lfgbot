from __future__ import annotations

from dataclasses import dataclass


class UnsetType:
    __slots__ = ()


UNSET: UnsetType = UnsetType()


@dataclass(slots=True)
class LobbyHostPatch:
    slots: int | UnsetType = UNSET
    min_rank: str | None | UnsetType = UNSET
    max_rank: str | None | UnsetType = UNSET
    party_code: str | None | UnsetType = UNSET
    party_code_public: bool | UnsetType = UNSET
    wanted_agents: list[str] | UnsetType = UNSET
    ranks_verified: bool | UnsetType = UNSET

    def is_empty(self) -> bool:
        return (
            self.slots is UNSET
            and self.min_rank is UNSET
            and self.max_rank is UNSET
            and self.party_code is UNSET
            and self.party_code_public is UNSET
            and self.wanted_agents is UNSET
            and self.ranks_verified is UNSET
        )
