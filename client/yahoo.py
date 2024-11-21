import json
import re
from typing import Any

from requests import Response

from client.base import BaseClient
from config.config import FantasyConfig
from exceptions import FantasyAuthError
from model.enums.platform_url import PlatformUrl
from model.league_data import LeagueData
from model.team import Team


class YahooClient(BaseClient):

    def __init__(self, league: LeagueData, config: FantasyConfig):
        super().__init__(league=league, config=config)
        self.session.headers.update({'cookie': self.config.get_cookie(self.league.platform)})
        self.crumb = self.config.get_crumb(self.league.platform)

    @property
    def team_url(self):
        return f"{self.config.get_platform_url(self.league.platform, PlatformUrl.FANTASY_HOCKEY)}/{self.league.id}/{self.league.team_id}"

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all(player in resp.text for player in self.league.locked_players):
            raise FantasyAuthError('Not logged in!')

    def get_team(self) -> Team:

        def get_match(resp: Response, match_str: str) -> str:
            match = re.search(f"\"{match_str}.*", resp.text)
            if match:
                return match.group(0)
        
        def convert_match_to_json(match_str: str) -> dict[str, Any]:
            return json.loads("{" + match_str[:-1] + "}")

        def parse_resp_data_to_dict(resp: Response, match_str: str) -> dict[str, Any]:
            raw_match = get_match(resp, match_str)
            #TODO: Use custom exception
            if not raw_match:
                raise ValueError(f"Could not match string in response: {match_str}")
            return convert_match_to_json(raw_match)

        resp_keys = {
            "varPRCurrTeamName": "name",
            "varPRLeague": "league_name",
            "varPRCurrTeamPlayers": "players",
        }
        mapped_resp_dict = {}

        resp = self.session.get(self.team_url)

        for resp_key, model_key in resp_keys.items():
            resp_key_dict = parse_resp_data_to_dict(resp, resp_key)
            mapped_resp_dict.update({model_key: resp_key_dict[resp_key]})
        
        return Team.from_dict(mapped_resp_dict)
        

    def add_player(self, add_id: str, drop_id: str = None) -> Response:
        data = {
            'stage': '3',
            'crumb': self.crumb,
            'stat1': 'P',
            'stat2': 'P',
            'apid': add_id,
        }
        if drop_id is not None:
            data['dpid'] = drop_id
        return self.session.post(f'{self.team_url}/addplayer', data=data)

    def place_waiver_claim(self, add_id: str, drop_id: str = None, faab: int = None) -> Response:
        data = {
            'stage': '3',
            'crumb': self.crumb,
            'stat1': 'P',
            'stat2': 'P',
            'apid': add_id,
        }

        if drop_id is not None:
            data['dpid'] = drop_id
        if faab is not None:
            data['faab'] = faab

        return self.session.post(f'{self.team_url}/addplayer', data=data)

    def cancel_waiver_claim(self, player_id: str) -> Response:
        data = {
            'stage': '2',
            'crumb': self.crumb,
            'claim_id': f'1_{player_id}_0',
            'mode': 'edit',
            'apid': player_id,
            's': 'Cancel Waiver'
        }
        return self.session.post(f'{self.team_url}/editwaiver', data=data)

    def get_player_name(self, player_id: str) -> Response:
        yahoo_nhl_url = self.config.get_platform_url(self.league.platform, PlatformUrl.NHL)
        response = self.session.get(f"{yahoo_nhl_url}/players/{player_id}/")
        return response.text.split("title>")[1].split("(")[0].strip()