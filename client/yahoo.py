import datetime
from doctest import OutputChecker
import json
import re
from typing import Any

import yahoo_fantasy_api as yfa
from requests import Response
from yahoo_oauth import OAuth2

from client.base import BaseClient
from config.config import FantasyConfig
from exceptions import (
    FantasyAuthError,
    AlreadyPlayedError,
    FantasyUnknownError,
    InvalidRosterPosition,
    MaxAddsError,
)
from model.enums.platform_url import PlatformUrl
from model.enums.position import Position
from model.league import League
from model.player import Player
from model.team import Team
from util.misc import prune_dict


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
        self.change_lineup()

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

    def change_lineup(self):
        cd = datetime.date(2024, 12, 13)
        plyrs = [
            {"player_id": 6751, "selected_position": Position.LW.value},  # Meier
            {"player_id": 8654, "selected_position": Position.BN.value},
        ]  # Holloway
        import ipdb

        ipdb.set_trace()
        self.team_handle.change_positions(cd, plyrs)

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
