from __future__ import annotations
from dataclasses import dataclass

from fantasy_manager.model.player import RosterPlayer


@dataclass(frozen=True)
class Team:
    team_id: str
    team_key: str
    name: str
    league_id: str
    faab_balance: int
    roster: list[RosterPlayer]

    @classmethod
    def from_dict(cls, data: dict) -> Team:
        """Convert a dictionary to a Team instance."""
        data["roster"] = [RosterPlayer.from_dict(p) for p in data["roster"]]
        return cls(**data)

    def __str__(self):
        return self.name
