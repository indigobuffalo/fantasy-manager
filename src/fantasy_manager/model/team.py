from __future__ import annotations

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from fantasy_manager.model.player import BasePlayer, FantasyPlayer


@dataclass(frozen=True)
class Team:
    team_id: str
    team_key: str
    name: str
    league_id: str
    faab_balance: int
    roster: list[FantasyPlayer]

    def __post_init__(self):
        if self.faab_balance < 0:
            raise ValueError("FAAB balance cannot be negative")

    @field_validator("faab_balance", mode="before")
    def convert_to_int(cls, v):
        if isinstance(v, str):
            return int(v)

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
