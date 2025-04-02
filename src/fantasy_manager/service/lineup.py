import copy
from datetime import date, timedelta
import logging

from pathlib import Path
from typing import Optional

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.client.nhl import NhlClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.game import Game
from fantasy_manager.model.league import League
from fantasy_manager.model.player import (
    AgnosticPlayer,
    LineupPlayer,
    RankedLineupPlayer,
    RankedPlayer,
)
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

        self.agnostic_player_cache = {}

    def _get_agnostic_player(self, player_id: int) -> AgnosticPlayer:
        """Get the player from the fantasy client.

        Args:
            player_id (int): The id of the player to get.

        Returns:
            AgnosticPlayer: The player object.
        """
        if player_id not in self.agnostic_player_cache:
            player = self.fantasy_client.get_player_by_id(player_id)
            self.agnostic_player_cache[player_id] = player
        return self.agnostic_player_cache[player_id]

    def _plays_in_games(self, player: LineupPlayer, games: list[Game]) -> bool:
        """Check if the player plays in any of the given games.

        Args:
            player (LineupPlayer): The player to check.
            games (list[Game]): The list of games to check against.

        Returns:
            bool: True if the player plays in any of the games, False otherwise.
        """
        nhl_team = self.fantasy_client.get_player_by_id(player.player_id).team.abbr
        for game in games:
            if nhl_team in (game.home_team.abbr, game.away_team.abbr):
                return True
        return False

    def _get_players_playing_on_date(
        self, fantasy_team: Team, game_date: date
    ) -> list[LineupPlayer]:
        """Get the players that are playing on a given date.

        Args:
            fantasy_team (Team): The fantasy team to check.
            game_date (date): The date to check.

        Returns:
            list[LineupPlayer]: The list of players that are playing on the given date.
        """
        games_on_date = self.nhl_client.get_games_by_date(game_date)
        return [
            player
            for player in fantasy_team.roster
            if self._plays_in_games(player, games_on_date)
        ]

    def create_ranked_lineup_player(
        self,
        lineup_player: LineupPlayer,
        ranked_player: Optional[RankedPlayer] = None,
    ) -> RankedLineupPlayer:
        """Create a RankedLineupPlayer instance from a LineupPlayer and RankedPlayer.

        Args:
            lineup_player (LineupPlayer): The LineupPlayer instance.
            ranked_player (Optional[RankedPlayer]): The RankedPlayer instance. Defaults to None.

        Returns:
            RankedLineupPlayer: The created RankedLineupPlayer instance.
        """
        if ranked_player is None:
            logger.warning(
                f"Player {lineup_player.name.full} not found in rankings, using default rank."
            )
            return RankedLineupPlayer(
                rank=self.config.DEFAULT_PLAYER_RANK, **lineup_player.model_dump()
            )
        return RankedLineupPlayer(
            rank=ranked_player.rank,
            **lineup_player.model_dump(),
        )

    def set_lineup_for_date(self, date_str: date, lineup_players: list[LineupPlayer]):
        # consider converting open_slots keys to enum instances
        open_slots = copy.deepcopy(self.league.roster_configuration)
        ranked_players = self.config.get_player_rankings(self.league.name_abbr)
        ranked_lineup_players = []

        def get_ranked_player_by_id(player_id: int) -> Optional[RankedLineupPlayer]:
            for rk_player in ranked_players:
                if rk_player.player_id == player_id:
                    return rk_player
            return None

        for lnp_player in lineup_players:
            ranked_player = get_ranked_player_by_id(lnp_player.player_id)
            ranked_lineup_players.append(
                self.create_ranked_lineup_player(
                    lineup_player=lnp_player, ranked_player=ranked_player
                )
            )

        import ipdb

        ipdb.set_trace()
        pass

    def automate_lineup(self, start: date, end: date):
        team = self.fantasy_client.get_team()
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        for dt in dates:
            players_playing = self._get_players_playing_on_date(team, dt)
            self.set_lineup_for_date(dt, players_playing)
