from turtle import home
from unittest.mock import Base
from pydantic import BaseModel

from fantasy_manager.model.nhl_team import NhlTeam


class Game(BaseModel):
    away_team: NhlTeam
    home_team: NhlTeam
    start_time_utc: str
