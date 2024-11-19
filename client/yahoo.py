from requests import Response

from client.base import BaseClient
from config.config import FantasyConfig
from exceptions import FantasyAuthError
from model.enums.platform import Platform
from model.enums.platform_url import PlatformUrl
from model.league_data import LeagueData


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

    def get_team_response(self):
        return self.session.get(self.team_url)

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