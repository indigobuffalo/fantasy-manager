from __future__ import annotations
from dataclasses import dataclass, asdict
import json


@dataclass(frozen=True)
class Player:
    id: str
    name: str

    def to_json(self) -> str:
        """Convert the Player instance to a JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_data: str) -> Player:
        """Create a Player instance from a JSON string."""
        data = json.loads(json_data)
        return cls(**data)
