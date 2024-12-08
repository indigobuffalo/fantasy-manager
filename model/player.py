from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import json

from model.player_name import PlayerName


class PlayerStatus(Enum):
    ACTIVE = ""
    DTD = "DTD"
    IR = "IR"
    NA = "NA"
    OUT = "O"
    LTIR = "IR-LT"


class PositionType(Enum):
    SKATER = "P"
    GOALIE = "G"


class Position(Enum):
    C = "C"
    LW = "LW"
    RW = "RW"
    D = "D"
    G = "G"
    UTIL = "UTIL"
    BN = "BN"
    IR = "IR"
    IR_PLUS = "IR+"


@dataclass(frozen=True)
class Player:
    player_id: str
    name: PlayerName
    status: PlayerStatus
    position_type: PositionType
    eligible_positions: list[Position]
    selected_position: Position

    def to_json(self) -> str:
        """Convert the Player instance to a JSON string."""
        return json.dumps(
            asdict(self), default=lambda o: o.value if isinstance(o, Enum) else o
        )

    @classmethod
    def from_dict(cls, data: dict) -> Player:
        """Create a Player instance from a JSON string."""
        data["name"] = PlayerName.from_dict(data["name"])
        data["status"] = PlayerStatus(data.get("status", "").upper())
        data["position_type"] = PositionType(data["position_type"].upper())
        data["eligible_positions"] = [
            p["position"].upper() for p in data["eligible_positions"]
        ]
        data["selected_position"] = (
            Position(data["selected_position"].upper())
            if "selected_position" in data
            else None
        )
        return cls(**data)
