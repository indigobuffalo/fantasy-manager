from datetime import date, timedelta
import logging

from pathlib import Path

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.client.nhl import NhlClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.game import Game
from fantasy_manager.model.league import League
from fantasy_manager.model.player import LineupPlayer
from fantasy_manager.model.team import Team

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

    def _plays_on_date(self, player: LineupPlayer, game_date: date) -> bool:
        games = self.nhl_client.get_games_by_date(game_date)
        pl_team = self.fantasy_client.get_player_by_id(player.player_id).team.abbr
        for game in games:
            if pl_team in (game.home_team.abbr, game.away_team.abbr):
                return True
        return False

    def _get_players_playing_on_date(self, team: Team, game_date: date):
        return [
            player for player in team.roster if self._plays_on_date(player, game_date)
        ]

    def automate_lineup(self, start: date, end: date):
        team = self.fantasy_client.get_team()
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        players_playing_by_date = {}
        for dt in dates:
            players_playing_by_date[dt] = [
                player for player in team.roster if self._plays_on_date(player, dt)
            ]
        import ipdb

        ipdb.set_trace()
        pass
