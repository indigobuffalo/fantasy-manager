from __future__ import annotations
from dataclasses import dataclass

from model.league_data import LeagueData


@dataclass(frozen=True)
class Team:
    name: str
    league_name: str
    players: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> Team:
        """Convert a dictionary to a Team instance."""
        data['players'] = [str(player_id) for player_id in data['players']]
        return cls(**data)
