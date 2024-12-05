from __future__ import annotations
from dataclasses import dataclass, asdict
import json

from model.enums.platform import Platform


@dataclass(frozen=True)
class League:
    id: str
    key: str
    locked_players: tuple
    name: str
    name_abbr: str
    platform: Platform
    team_id: int
    team_name: str

    @classmethod
    def from_dict(cls, data: dict) -> League:
        """Convert a dictionary to a League instance, ensuring correct types."""
        data["platform"] = Platform[data["platform"].upper()]
        return cls(**data)

    def to_json(self) -> str:
        """Convert the League instance to a JSON string."""

        def custom_encoder(obj):
            if isinstance(obj, Platform):
                return obj.value
            # TODO: use custom exception
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serializable"
            )

        return json.dumps(asdict(self), default=custom_encoder)

    @classmethod
    def from_json(cls, json_data: str) -> League:
        """Create a League instance from a JSON string."""
        data = json.loads(json_data)
        data["platform"] = Platform(data["platform"])
        return cls(**data)
