from dataclasses import dataclass
from model.enums.platform import Platform


@dataclass(frozen=True)
class LeagueData:
    id: str
    locked_players: tuple
    name: str
    platform: Platform
    team_id: int
    team_name: str
