from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import json
from typing import Optional

from model.enums.position import Position, PositionType
from model.enums.player_status import PlayerStatus


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

    @classmethod
    def from_roster_api(cls, data: dict) -> Player:
        """Create a Player instance from the roster API data."""
        data["name"] = {"full": data["name"]}
        data["eligible_positions"] = [
            {"position": pos} for pos in data["eligible_positions"]
        ]
        return cls.from_dict(data)
