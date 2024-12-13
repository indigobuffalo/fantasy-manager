import datetime
import json
import re
from typing import Any

import yahoo_fantasy_api as yfa
from requests import Response
from yahoo_oauth import OAuth2

from fantasy_manager.client.base import BaseClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    FantasyAuthError,
    AlreadyPlayedError,
    FantasyUnknownError,
    InvalidRosterPosition,
    MaxAddsError,
    NotOnRosterError,
)
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.model.enums.position import Position
from fantasy_manager.model.league import League
from fantasy_manager.model.player import Player, LineupPlayer
from fantasy_manager.model.lineup import Lineup
from fantasy_manager.model.team import Team
from fantasy_manager.util.dataclass_utils import prune_dict


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
        self.leage_handle = yfa.Game(self.session_context, "nhl").to_league(
            self.league.key
        )
        self.team_handle = self.leage_handle.to_team(self.leage_handle.team_key())

    def refresh(self):
        """Refreshes client auth and related handles."""
        self._refresh_context()

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all(player in resp.text for player in self.league.locked_players):
            raise FantasyAuthError("Not logged in!")

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
        data = {}

        data.update(self.leage_handle.teams()[self.leage_handle.team_key()])

        yfa_team = self.leage_handle.to_team(self.leage_handle.team_key())
        data["roster"] = yfa_team.roster()
        data["league_id"] = yfa_team.league_id

        return Team.from_roster_api(prune_dict(Team, data))

    def add_player(self, add_id: str, drop_id: str = None) -> None:
        try:
            match drop_id:
                case None:
                    self.team_handle.add_player(add_id)
                case _:
                    self.team_handle.add_and_drop_players(
                        add_player_id=add_id, drop_player_id=drop_id
                    )
        except Exception as ex:
            exc_msg = str(ex)
            match exc_msg:
                case str() if "no longer qualifies for that position" in exc_msg:
                    raise InvalidRosterPosition(add_id, str(ex))
                case str() if "player has already played and is no longer" in exc_msg:
                    raise AlreadyPlayedError(add_id)
                case str() if "You have reached the weekly limit" in exc_msg:
                    raise MaxAddsError()
                case str() if f"is not on team {self.league.team_name}" in exc_msg:
                    raise NotOnRosterError(add_id, str(ex))
                case _:
                    raise FantasyUnknownError(
                        f"Error adding player '{add_id}':\n\n{exc_msg}"
                    )

    def place_waiver_claim(
        self, add_id: str, drop_id: str = None, faab: int = None
    ) -> Response:
        data = {
            "stage": "3",
            "crumb": self.crumb,
            "stat1": "P",
            "stat2": "P",
            "apid": add_id,
        }

        if drop_id is not None:
            data["dpid"] = drop_id
        if faab is not None:
            data["faab"] = faab

        return self.session.post(f"{self.team_url}/addplayer", data=data)

    def cancel_waiver_claim(self, player_id: str) -> Response:
        data = {
            "stage": "2",
            "crumb": self.crumb,
            "claim_id": f"1_{player_id}_0",
            "mode": "edit",
            "apid": player_id,
            "s": "Cancel Waiver",
        }
        return self.session.post(f"{self.team_url}/editwaiver", data=data)

    def get_player_by_id(self, player_id: int) -> Player:
        yfa_player = self.leage_handle.player_details(player_id)[0]
        return Player.from_dict(prune_dict(Player, yfa_player))
