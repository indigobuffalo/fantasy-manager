from __future__ import annotations
from dataclasses import dataclass

from model.player import Player


@dataclass(frozen=True)
class Team:
    team_id: str
    team_key: str
    name: str
    league_id: str
    faab_balance: int
    roster: list[Player]

    @classmethod
    def from_dict(cls, data: dict) -> Team:
        """Convert a dictionary to a Team instance."""
        data["roster"] = [Player.from_dict(p) for p in data["roster"]]
        return cls(**data)

    @classmethod
    def from_roster_api(cls, data: dict) -> Team:
        """Create a Team instance from roster API data."""
        data["roster"] = [Player.from_roster_api(p) for p in data["roster"]]
        return cls(
            team_id=data["team_id"],
            team_key=data["team_key"],
            name=data["name"],
            league_id=data["league_id"],
            faab_balance=data["faab_balance"],
            roster=data["roster"],
        )

    def __str__(self):
        return self.name
