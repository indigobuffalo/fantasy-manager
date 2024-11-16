#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python
from time import sleep

import re
import requests
import yaml
from datetime import datetime, date
from pathlib import Path

from config.config import FantasyConfig
from headers import COOKIE, CRUMB
from exceptions import AlreadyAddedError, AlreadyPlayedError, MaxAddsError, FantasyAuthError, \
    FantasyUnknownError, UserAbortError, YahooFantasyError, NotOnRosterError, UnintendedWaiverAddError
from util.time_utils import current_season_years, sleep_until, upcoming_midnight


PROJECT_DIR = Path(__file__).parent.absolute()

ALREADY_PLAYED_MESSAGE = 'player has already played and is no longer'
WEEKLY_LIMIT_MESSAGE = 'You have reached the weekly limit'
WAIVER_CLAIM_PLACED = 'created%2520a%2520waiver%2520claim%2520for'

def get_player_name(player_id: str) -> str:
    """Parses the dom of yahoo player page to get the players name

    Args:
        player_id (str): The yahoo player id.

    Returns:
        str: The player's name
    """
    if not player_id:
       return "nobody"
    response = requests.get(f"http://sports.yahoo.com/nhl/players/{player_id}/")
    return response.text.split("title>")[1].split("(")[0].strip()


class RosterController:
    
    def __init__(self, league_name: str):
        self.league = FantasyConfig.get_league_data(league_name)
        self.team_url = f'{FantasyConfig.get_base_url(self.league.platform)}/{self.league.id}/{self.league.team_id}'

        yr_one, yr_two = current_season_years()
        self.rosters_dir = PROJECT_DIR / 'data' / 'rosters' / f"{yr_one}-{yr_two}" / self.league.id

        self.session = requests.Session()
        self.session.headers.update({'cookie': COOKIE})

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all(player in resp.text for player in self.league.locked_players):
            raise FantasyAuthError('Not logged in!')
    
    def are_rostered(self, player_ids: list[str]) -> list[str]:
        unrostered = list()
        for player_id in player_ids:
            if not self.is_rostered(player_id):
                unrostered.append(player_id)
        return unrostered

    def is_rostered(self, player_id: str) -> bool:
        pattern = f"varPRCurrTeamPlayers.*{player_id}.*"
        team_response = self.session.get(self.team_url)
        return re.search(pattern, team_response.text)

    # TODO: FIX THIS on_waivers method
    def on_waivers(self, player_id):
        add_response = self.session.get(f"{self.team_url}/addplayer?apid={player_id}")
        return "Claim Player From Waivers" in add_response.text

    def _check_add_response(self, add_id, resp):
        if ALREADY_PLAYED_MESSAGE in resp.text:
            raise AlreadyPlayedError(add_id)
        if WEEKLY_LIMIT_MESSAGE in resp.text:
            raise MaxAddsError("Already reached max adds for the week!")
        if WAIVER_CLAIM_PLACED in resp.text:
            raise UnintendedWaiverAddError("Accidentally added player from waivers.")
        if not self.is_rostered(add_id):
            raise FantasyUnknownError(f"Error - player '{add_id}' not added.")

    def cancel_waiver_claim(self, player_id: str):
        data = {
            'stage': '2',
            'crumb': CRUMB,
            'claim_id': f'1_{player_id}_0',
            'mode': 'edit',
            'apid': player_id,
            's': 'Cancel Waiver'
        }
        cancel_response = self.session.post(f'{self.team_url}/editwaiver', data=data)
        if cancel_response.status_code == 200:
            print("Successfully canceled waiver claim")
        else:
            import ipdb; ipdb.set_trace()
        return

    @staticmethod
    def confirm_proceed():
        answer = input("Continue?\n")
        if answer.upper() in ["Y","YES"]:
            return
        else:
            raise UserAbortError

    # def log_inputs(add_id: str, drop_id: str = None, )
    
    def add_player_with_delay(self, add_id: str, drop_id: str = None, start: str = None, faab: int = None):
        add_dt = datetime.fromisoformat(start) if start else upcoming_midnight()
        if add_dt <= datetime.now():
            self.confirm_proceed()
        sleep_until(add_dt)
        self.add_player(add_id=add_id, drop_id=drop_id, faab=faab)

    def add_player(self, add_id: str, drop_id: str = None, faab: int = None):
        print(f"Adding {get_player_name(add_id)} and dropping {get_player_name(drop_id)}")

        if faab is not None:
            print(f"FAAB bid: ${faab}")
        if self.is_rostered(add_id):
            raise AlreadyAddedError(add_id)
        if drop_id is not None and not self.is_rostered(drop_id):
            raise NotOnRosterError(drop_id)

        # TODO: determine how to only add a player once they clear waivers
        # if self.on_waivers(add_id):
        #     raise OnWaiversError(f"Player {add_id} is on waivers!")

        data = {
            'stage': '3',
            'crumb': CRUMB,
            'stat1': 'P',
            'stat2': 'P',
            'apid': add_id,
        }
        if drop_id is not None:
            data['dpid'] = drop_id
        if faab is not None:
            data['faab'] = faab

        while True:
            print(f'The time is {datetime.now()}.')
            if drop_id is not None and not self.is_rostered(drop_id):
                print("Player to drop has already been dropped.")
                return
            try:
                add_response = self.session.post(f'{self.team_url}/addplayer', data=data)
                self._check_add_response(add_id, add_response)
                print(f"Success!  Player {add_id} is now on roster.")
                return
            except UnintendedWaiverAddError:
                waiver_wait_min = 30
                print('Accidentally added player to waivers, canceling now.')
                self.cancel_waiver_claim(add_id)
                print(f"Waiting {waiver_wait_min} minutes for waivers to clear "
                      f"before trying to add player {add_id} from FA again.")
                sleep(waiver_wait_min * 60)
                continue
            except YahooFantasyError as err:
                print(f'Error:{err}\nSleeping 0.1 seconds.')
                sleep(0.1)
                continue

    def edit_lineup(self, roster_filename: str, game_date: date):
        data = {
            'ret': 'swap',
            'date': datetime.strftime(game_date, '%Y-%m-%d'),
            'stat1': 'S',
            'stat2': 'D',
            'crumb': CRUMB,
        }
        with open(self.rosters_dir / roster_filename) as roster_file:
            roster = yaml.safe_load(roster_file)
        data.update(roster)

        return self.session.post(f'{self.team_url}/editroster', data=data)
