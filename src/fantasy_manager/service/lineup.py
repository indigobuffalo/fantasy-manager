import logging

from pathlib import Path

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig

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
        roster = self.client.get_team().roster
        import ipdb

        ipdb.set_trace()
        pass
