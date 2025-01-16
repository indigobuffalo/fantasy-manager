from __future__ import annotations
from dataclasses import dataclass

from fantasy_manager.model.player import BasePlayer, RosterPlayer


@dataclass(frozen=True)
class Team:
    team_id: str  # league_team
    team_key: str  # league_team
    name: str  # league_team
    league_id: str
    faab_balance: int  # league_team
    roster: list[RosterPlayer]

    def __post_init__(self):
        if self.faab_balance < 0:
            raise ValueError("FAAB balance cannot be negative")

    @classmethod
    def from_dict(cls, data: dict) -> Team:
        """Convert a dictionary to a Team instance."""
        data["roster"] = [RosterPlayer.from_dict(p) for p in data["roster"]]
        data["faab_balance"] = int(data["faab_balance"])
        return cls(**data)

    def __str__(self):
        # """
        return self.name

    def has_player(self, player: BasePlayer) -> bool:
        """Check if a player is on the team by player_id.

        Args:
            player_id (int): The player to check the team for.

        Returns:
            bool: Returns True if the player is on the team, else False.
        """
        return player.player_id in (p.player_id for p in self.roster)
