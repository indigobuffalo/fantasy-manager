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
        # """
        return self.name

    def has_player(self, player_id: int) -> bool:
        """Check if a player is on the team by player_id.

        Args:
            player_id (int): The player to check the team for.

        Returns:
            bool: Returns True if the player is on the team, else False.
        """
        return player_id in (p.player_id for p in self.roster)
