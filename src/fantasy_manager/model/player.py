from __future__ import annotations
import logging
from typing import Optional

from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from fantasy_manager.model.enums.position import Position, PositionType
from fantasy_manager.model.enums.player_status import PlayerStatus
from fantasy_manager.model.nhl_team import NhlTeam


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayerName:
    full: str
    first: Optional[str] = None
    last: Optional[str] = None
    ascii_first: Optional[str] = None
    ascii_last: Optional[str] = None

    def __str__(self):
        return self.full


class BasePlayer(BaseModel, validate_assignment=True):
    """Base representation of a player.

    Attrs:
        player_id(int)  : The platform's identifier for the player.
        name(PlayerName): The name of the player
    """

    player_id: int
    name: PlayerName

    def __str__(self):
        return str(self.name.full)


class PositionedPlayer(BasePlayer):
    """Player model with generalized (i.e. not lineup-specific) position assignments.

    Attrs:
        position_type (PositionType):         Whether the player is a skater or goalie.
        eligible_positions (list[Position]):  The positions the player is eligible for.
    """

    position_type: PositionType
    eligible_positions: list[Position]
    status: Optional[PlayerStatus] = PlayerStatus.ACTIVE


class AgnosticPlayer(PositionedPlayer):
    """Represents player details outside the context of a specific fantasy team.
    This player data is fetched from player-specific api endpoint.

    Attrs:
        team (NhlTeam): The player's NHL team.
    """

    team: NhlTeam


class LineupPlayer(PositionedPlayer):
    """Player model representing a player in a fantasy lineup.
    This player data comes from the yfa team.roster endpoint.

    Attributes:
        selected_position (Position):  The player's currently selected position in the lineup.
    """

    selected_position: Position


class RankedLineupPlayer(LineupPlayer):
    """Player model representing a player in a fantasy lineup with a custom assigned rank.

    Attributes:
        rank (int):  The user assigned rank of the player on a scale of 1-100.
                     Lowest rank is 1, highest is 100.
    """

    rank: int
