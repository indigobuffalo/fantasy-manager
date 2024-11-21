from __future__ import annotations
from dataclasses import dataclass

from model.enums.platform import Platform


@dataclass(frozen=True)
class LeagueData:
    id: str
    locked_players: tuple
    name: str
    name_abbr: str
    platform: Platform
    team_id: int
    team_name: str

    @classmethod
    def from_dict(cls, data: dict) -> LeagueData:
        """Convert a dictionary to a LeagueData instance, ensuring correct types."""
        data["platform"] = Platform[data["platform"].upper()]
        return cls(**data)
