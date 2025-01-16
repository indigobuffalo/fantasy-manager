from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import json
from typing import Optional

from fantasy_manager.exceptions import InvalidModelDataError
from fantasy_manager.model.enums.position import Position, PositionType
from fantasy_manager.model.enums.player_status import PlayerStatus
from fantasy_manager.util.dataclass_utils import filtered_asdict, prune_dict


@dataclass(frozen=True)
class PlayerName:
    full: str
    first: Optional[str] = None
    last: Optional[str] = None
    ascii_first: Optional[str] = None
    ascii_last: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> PlayerName:
        """Convert a dictionary to a PlayerName instance."""
        return cls(**data)

    def __str__(self):
        return self.full

    def __len__(self):
        return len(self.full)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlayerName):
            return NotImplemented
        return (self.last, self.first) == (other.last, other.first)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PlayerName):
            return NotImplemented
        return self.full < other.full

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PlayerName):
            return NotImplemented
        return self.full > other.full


@dataclass(frozen=True)
class BasePlayer:
    """Base representation of a player.

    Attrs:
        name(PlayerName): The name of the player
    """

    player_id: int
    name: PlayerName

    def __str__(self):
        return str(self.name)

    @classmethod
    def from_dict(cls, data: dict) -> BasePlayer:
        """Create a BasePlayer instance from a dict."""

        name_data = data["name"]
        match name_data:
            case str():
                name = PlayerName(full=name_data)
            case dict():
                name = PlayerName.from_dict(name_data)
            case _:
                raise InvalidModelDataError(
                    f"Unable to instantiate a player name from: '{name_data}'"
                )

        return cls(player_id=int(data["player_id"]), name=name)

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass(frozen=True)
class PositionedPlayer(BasePlayer):
    """Player model with generalized (i.e. not lineup-specific) position assignments.

    Attrs:
        position_type (PositionType):         Whether the player is a skater or goalie.
        status (PlayerStatus):                The player's status, e.g. 'IR', 'DTD', 'O', etc.
        eligible_positions (list[Position]):  The positions the player is eligible for.
    """

    position_type: PositionType
    status: PlayerStatus
    eligible_positions: list[Position]

    @classmethod
    def from_dict(cls, data: dict) -> ApiPlayer:
        """Create a PositionedPlayer instance from a dict."""
        base_player = BasePlayer.from_dict(data)
        player_data = {
            **base_player.__dict__,
            "position_type": PositionType(data["position_type"].upper()),
            "status": PlayerStatus(data.get("status", "").upper()),
            "eligible_positions": [
                Position(p.upper()) for p in data["eligible_positions"]
            ],
        }
        return cls(**player_data)


@dataclass(frozen=True)
class ApiPlayer(PositionedPlayer):
    """Represents comprhensive player details outside the context of a given lineup.
    This player data is fetched from player-specific api endpoint.

    Attrs:
        team (str):              The player's team.
        team_abbr (str):         The player's team's abbreviation.
    """

    team: str
    team_abbr: str

    def to_json(self) -> str:
        """Convert the Player instance to a JSON string."""
        return json.dumps(
            asdict(self), default=lambda o: o.value if isinstance(o, Enum) else o
        )

    @classmethod
    def from_dict(cls, data: dict) -> ApiPlayer:
        """Convert a dictionary into an APIPlayer instance.

        Args:
            data (dict): Input dictionary containing player data.

        Returns:
            ApiPlayer:  The player instantiated.
        """
        positioned_player = PositionedPlayer.from_dict(data)
        player_data = {
            **data,
            **positioned_player.__dict__,
        }
        return cls(**player_data)


@dataclass(frozen=True)
class RosterPlayer(PositionedPlayer):
    """Player model with general, non-lineup specific position assignments.
    This player data is fetched from the yfa team.roster endpoint.

    Attributes:
        selected_position (Position):  The player's currently selected position in the lineup.
    """

    selected_position: Position

    @classmethod
    def from_dict(cls, data: dict) -> RosterPlayer:
        """Convert a dictionary into a RosterPlayer instance"""
        base_player = BasePlayer.from_dict(data)
        positioned_player = PositionedPlayer.from_dict(data)
        player_data = {
            **base_player.__dict__,
            **positioned_player.__dict__,
            "selected_position": Position(data["selected_position"].upper()),
        }
        return cls(**player_data)


@dataclass(frozen=True)
class RankedPlayer(BasePlayer):
    """Model representing a player and their custom assigned ranking

    Attrs:
      ranking (int): Custom assigned ranking from 0-100
    """

    ranking: int


@dataclass(frozen=True)
class LineupPlayer(BasePlayer):
    ranking: int
    selected_position: Optional[Position] = None

    def to_json(self) -> str:
        """Convert the LineupPlayer instance to a JSON string for the lineup API."""
        return json.dumps(
            filtered_asdict(self, exclude={"name", "ranking"}),
            default=lambda o: o.value if isinstance(o, Enum) else o,
        )
