import logging
from time import sleep

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyAddedError,
    FantasyUnknownError,
    NotOnRosterError,
    OnAnotherTeamError,
    TimeoutExceededError,
)
from fantasy_manager.model.player import Player
from fantasy_manager.util.temporal import sleep_until, sleep_verbose

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, league_name: str):
        self.config = FantasyConfig()
        self.league = self.config.get_league(league_name)
        self.client = ClientFactory.get_client(
            platform=self.league.platform, league=self.league, config=self.config
        )
        self.client.refresh()
        self.timeout_seconds = self.config.TIMEOUT_SECONDS

    def automate_lineup(self):
        lineup = self.config.get_lineup()
        pass
