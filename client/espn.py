from client.base import BaseClient
from config.config import FantasyConfig
from model.league_data import LeagueData
from model.team import Team


class EspnClient(BaseClient):

    def __init__(self, league: LeagueData, config: FantasyConfig):
        self.super.__init__(league=league, config=config)

    @property
    def __team_url(self):
        """The url to the manager's fantasy team page .
        """
        pass

    def get_team(self) -> Team:
        """Fetch team response.
        """
        pass

    def check_current_auth(self):
        """Ensure the current session is authenticated.
        """
        pass

    def add_player(self):
        """Add a player to the manager's roster.
        """
        pass
