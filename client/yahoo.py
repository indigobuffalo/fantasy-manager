import json
import re
from typing import Any

from requests import Response

from client.base import BaseClient
from config.config import FantasyConfig
from exceptions import (
    FantasyAuthError,
    AlreadyPlayedError,
    MaxAddsError,
    UnintendedWaiverAddError,
    FantasyUnknownError,
)
from model.enums.platform_url import PlatformUrl
from model.league import League
from model.player import Player
from model.team import Team


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

    @property
    def team_url(self):
        platform_url = self.config.get_platform_url(
            self.league.platform, PlatformUrl.FANTASY_HOCKEY
        )
        return f"{platform_url}/{self.league.id}/{self.league.team_id}"

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all(player in resp.text for player in self.league.locked_players):
            raise FantasyAuthError("Not logged in!")

    def get_team(self) -> Team:
        def parse_resp_item(resp: Response, match_str: str) -> dict[str, Any]:
            match = re.search(f'"{match_str}.*', resp.text)
            if not match:
                raise TeamDataNotFoundError(match_str)
            return json.loads("{" + match.group(0)[:-1] + "}")

        resp_keys_to_model_keys = {
            "varPRCurrTeamName": "name",
            "varPRLeague": "league_name",
            "varPRCurrTeamPlayers": "players",
        }

        parsed_response = {}
        resp = self.session.get(self.team_url)
        for resp_key, model_key in resp_keys_to_model_keys.items():
            resp_item = parse_resp_item(resp, resp_key)
            parsed_response.update({model_key: resp_item[resp_key]})

        return Team.from_dict(parsed_response)

    def add_player(self, add_id: str, drop_id: str = None) -> None:
        data = {
            "stage": "3",
            "crumb": self.crumb,
            "stat1": "P",
            "stat2": "P",
            "apid": add_id,
        }
        if drop_id is not None:
            data["dpid"] = drop_id
        resp = self.session.post(f"{self.team_url}/addplayer", data=data)

        if "player has already played and is no longer" in resp.text:
            raise AlreadyPlayedError(add_id)
        if "You have reached the weekly limit" in resp.text:
            raise MaxAddsError("Already reached max adds for the week!")
        if "created%2520a%2520waiver%2520claim%2520for" in resp.text:
            raise UnintendedWaiverAddError("Accidentally added player from waivers.")
        # if not self.is_rostered(add_id):
        # raise FantasyUnknownError(f"Error - player '{add_id}' not added.")

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

    def get_player(self, player_id: str) -> Player:
        yahoo_nhl_url = self.config.get_platform_url(
            self.league.platform, PlatformUrl.NHL
        )
        response = self.session.get(f"{yahoo_nhl_url}/players/{player_id}/")
        return Player(
            id=player_id, name=response.text.split("title>")[1].split("(")[0].strip()
        )
