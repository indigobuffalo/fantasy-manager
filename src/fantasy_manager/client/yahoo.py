import datetime
import json
import logging
from typing import Optional

import ipdb.stdout
import yahoo_fantasy_api as yfa
from requests import Response
from yahoo_oauth import OAuth2

from fantasy_manager.client.base import BaseClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyPlayedError,
    FantasyAuthError,
    FantasyUnknownError,
    InvalidRosterPosition,
    MaxAddsError,
    NotOnRosterError,
    OnAnotherTeamError,
)
from fantasy_manager.model.dto.team import RawTeamDto
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.model.league import League
from fantasy_manager.model.player import ApiPlayer
from fantasy_manager.model.lineup import Lineup
from fantasy_manager.model.team import Team
from fantasy_manager.transform.yahoo import (
    transform_player_by_id_to_api_player,
    transform_yfa_team_data_to_team,
)


logger = logging.getLogger(__name__)


class TeamDataNotFoundError(Exception):
    """Error thrown when the team response does not contain expected data"""

    def __init__(self, match_str: str):
        self.message = f"Could not find {match_str} in team response"
        super().__init__(self.message)


class YahooClient(BaseClient):
    """Class for interacting with Yahoo APIs

    Args:
        BaseClient (_type_): The parent client class.
    """

    def __init__(self, league: League, config: FantasyConfig):
        super().__init__(league=league, config=config)
        self.session.headers.update(
            {"cookie": self.config.get_cookie(self.league.platform)}
        )
        self.crumb = self.config.get_crumb(self.league.platform)
        self._refresh_context()

    @property
    def team_url(self):
        platform_url = self.config.get_platform_url(
            self.league.platform, PlatformUrl.FANTASY_HOCKEY
        )
        return f"{platform_url}/{self.league.id}/{self.league.team_id}"

    def _refresh_context(self):
        """Sets up the session context and related handles."""
        self.session_context = OAuth2(
            None, None, from_file=self.config.YAHOO_CREDS_FILE
        )
        self.league_handle = yfa.Game(self.session_context, "nhl").to_league(
            self.league.key
        )
        self.team_handle = self.league_handle.to_team(self.league_handle.team_key())

    def _check_locked_players(self) -> None:
        """Ensure all expected players are on roster.

        Raises:
            FantasyAuthError: If not all locked players are on roster.
        """
        rostered_players_ids = [p["player_id"] for p in self.team_handle.roster()]
        locked_player_ids = self.league.locked_players
        if not all(locked in rostered_players_ids for locked in locked_player_ids):
            raise FantasyAuthError("Failed to load team. Check auth.")

    def refresh(self):
        """Refresh client auth and related handles."""
        self._refresh_context()
        # TODO: moved locked players check to service
        self._check_locked_players()

    def set_lineup(self, lineup: Lineup, lineup_date: datetime.date) -> None:
        """Set lineup for the given date.

        Args:
            lineup (Lineup): lineup of players and their selected positions
            lineup_date (datetime.date): the date to set the lineup
        """
        lineup_date = datetime.date(2024, 12, 12)
        # lineup = Lineup(
        # players=[
        # LineupPlayer(player_id=6751, name="Timo Meier", selected_position=Position.BN.value, ranking=85),
        # LineupPlayer(player_id=8654, name="Dylan Holloway", selected_position=Position.LW.value, ranking=82),
        # LineupPlayer(player_id=8654, name="Mark Stone", selected_position=Position.RW.value, ranking=91),
        # LineupPlayer(player_id=6756, name="Jake Debrusk", selected_position=Position.RW.value, ranking=86),
        # ]
        # )
        as_json = lineup.to_json()
        self.team_handle.change_positions(lineup_date, json.loads(as_json))

    def get_team(self) -> Team:
        league_team = self.league_handle.teams()[self.league_handle.team_key()]
        team = self.league_handle.to_team(self.league_handle.team_key())
        raw_data_dto = RawTeamDto.from_raw_data(league_team, team)
        transformed = transform_yfa_team_data_to_team(raw_data_dto)
        team = Team.from_dict(transformed)
        return Team

    @staticmethod
    def _handle_client_error(add_id: int, err: Exception):
        add_id_str = str(add_id)
        msg = str(err)
        match msg:
            case str() if "no longer qualifies for that position" in msg:
                raise InvalidRosterPosition(add_id_str, msg)
            case str() if "player has already played" in msg:
                raise AlreadyPlayedError(add_id_str)
            case str() if "player is currently on another team" in msg:
                raise OnAnotherTeamError(add_id_str)
            case str() if "reached the weekly limit" in msg:
                raise MaxAddsError()
            case str() if f"is not on team" in msg:
                raise NotOnRosterError(add_id_str, msg)
            case _:
                raise FantasyUnknownError(
                    f"Error adding player '{add_id_str}':\n\n{msg}"
                )

    def add_player(self, add_id: int) -> None:
        try:
            self.team_handle.add_player(add_id)
        except Exception as err:
            self._handle_client_error(add_id=add_id, err=err)

    def drop_player(self, drop_id: int) -> None:
        try:
            self.team_handle.drop_player(drop_id)
        except Exception as err:
            logging.info(f"Error dropping player: {err}")
            raise

    def replace_player(self, add_id: int, drop_id: Optional[int] = None) -> None:
        try:
            self.team_handle.add_and_drop_players(
                add_player_id=add_id, drop_player_id=drop_id
            )
        except Exception as err:
            self._handle_client_error(add_id=add_id, err=err)

    def place_waiver_claim(
        self, add_id: int, drop_id: Optional[int] = None, faab: int = None
    ) -> Response:
        pass

    def cancel_waiver_claim(self, player_id: int) -> None:
        pass

    def get_player_by_id(self, player_id: int) -> ApiPlayer:
        """Fetches player from yfa's League.get_player_details endpoint.

        Note: we ignore some data coming back from this endpoint which we may
        want to use in the future.  E.g. advanced stats, points, logo_url, etc.

        Args:
            player_id (int): The id of the player.

        Returns:
            ApiPlayer: an ApiPlayer model instance.
        """
        yfa_player = self.league_handle.player_details(player_id)[0]
        transformed = transform_player_by_id_to_api_player(yfa_player)
        return ApiPlayer.from_dict(transformed)
