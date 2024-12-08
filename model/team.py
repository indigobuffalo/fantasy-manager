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
        data["roster"] = [Player.from_dict(player) for player in data["roster"]]
        return cls(**data)

    def __str__(self):
        return self.name
