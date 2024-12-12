"""Represents the data accepted by yfa calls to change roster positions.  Similar to model.Team, but slimmer"""
from __future__ import annotations
from enum import Enum
import json
from typing import List
from dataclasses import dataclass, asdict

from fantasy_manager.model.player import LineupPlayer


@dataclass
class Lineup:
    players: List[LineupPlayer]

    def as_dict(self) -> str:
        """Convert the Roster instance to a JSON string for the lineup API."""
        return json.dumps(
            [json.loads(player.to_json()) for player in self.players],
            default=lambda o: o.value if isinstance(o, Enum) else o,
        )

    def to_json(self) -> str:
        """Convert the Roster instance to a JSON string for the lineup API."""
        return json.dumps(
            [json.loads(player.to_json()) for player in self.players],
            default=lambda o: o.value if isinstance(o, Enum) else o,
        )
