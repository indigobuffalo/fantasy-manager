from datetime import date
import logging

from pathlib import Path

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.client.nhl import NhlClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.league import League

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class LineupService:
    def __init__(
        self,
        league: League,
        fantasy_client: BaseFantasyClient,
        nhl_client: NhlClient,
        config: FantasyConfig,
    ):
        self.config = config
        self.league = league
        self.nhl_client = nhl_client

        self.fantasy_client = fantasy_client
        self.fantasy_client.refresh()

        self.timeout_seconds = self.config.ADD_PLAYER_TIMEOUT_SECONDS

    def automate_lineup(self, start: date, end: date):
        roster = self.fantasy_client.team_handle.roster()
        games = self.nhl_client.get_games_by_date(start.strftime("%Y-%m-%d"))

        import ipdb

        ipdb.set_trace()
        pass
