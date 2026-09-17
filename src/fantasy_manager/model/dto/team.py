from __future__ import annotations
from typing import Protocol, List, Dict, Any

from pydantic.dataclasses import dataclass


class RosterDataSource(Protocol):
    league_id: str

    def roster(self) -> List[Dict[str, Any]]:
        ...


@dataclass
class RawTeamDto:
    """DTO for raw team data fetched from the YFA client."""

    league_id: str
    roster: List[Dict[str, Any]]
    additional_data: Dict[str, Any]

    @classmethod
    def from_raw_data(cls, league_team: dict, team: RosterDataSource) -> RawTeamDto:
        """Create a DTO instance from raw YFA client data."""
        return cls(
            league_id=team.league_id,
            roster=team.roster(),
            additional_data={k: v for k, v in league_team.items()},
        )
