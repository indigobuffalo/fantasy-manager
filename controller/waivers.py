#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python
import re
from time import sleep
from typing import Optional

from datetime import datetime, date
from pathlib import Path

from client.factory import ClientFactory
from config.config import FantasyConfig
from exceptions import AlreadyAddedError, AlreadyPlayedError, MaxAddsError, \
    FantasyUnknownError, UserAbortError, NotOnRosterError, UnintendedWaiverAddError
from model.enums.platform_url import PlatformUrl
from util.time_utils import sleep_until, upcoming_midnight


PROJECT_DIR = Path(__file__).parent.absolute()

ALREADY_PLAYED_MESSAGE = 'player has already played and is no longer'
WEEKLY_LIMIT_MESSAGE = 'You have reached the weekly limit'
WAIVER_CLAIM_PLACED = 'created%2520a%2520waiver%2520claim%2520for'


class RosterController:
    
    def __init__(self, league_name: str):
        self.config = FantasyConfig
        self.league = self.config.get_league_data(league_name)
        self.client = ClientFactory.get_client(platform=self.league.platform, league=self.league, config=self.config)

    def are_rostered(self, player_ids: list[str]) -> list[str]:
        unrostered = list()
        for player_id in player_ids:
            if not self.is_rostered(player_id):
                unrostered.append(player_id)
        return unrostered

    def is_rostered(self, player_id: str) -> bool:
        team = self.client.get_team()
        return player_id in team.players

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
        cancel_response = self.client.cancel_waiver_claim(player_id)
        if cancel_response.status_code == 200:
            print("Successfully canceled waiver claim")
        else:
            import ipdb; ipdb.set_trace()
        return

    @staticmethod
    def confirm_proceed():
        answer = input("Continue? [ y | n ]\n")
        if answer.upper() in ["Y","YES"]:
            return
        else:
            raise UserAbortError

    def log_inputs(self, add_id: str, drop_id: str = None, faab: Optional[int] = None) -> None:
        print(f"League: {self.league.name}")
        print(f"Add: {self.client.get_player_name(add_id)}")
        print(f"Drop: {self.client.get_player_name(drop_id)}")
        if faab is not None:
            print(f"FAAB bid: ${faab}")
    
    def add_player_with_delay(self, add_id: str, drop_id: str = None, start: str = None, faab: int = None):
        add_dt = datetime.fromisoformat(start) if start else upcoming_midnight()
        sleep_until(add_dt)
        self.add_player(add_id=add_id, drop_id=drop_id, faab=faab)

    def add_player(self, add_id: str, drop_id: str = None, faab: int = None):
        if self.is_rostered(add_id):
            raise AlreadyAddedError(add_id)
        if drop_id is not None and not self.is_rostered(drop_id):
            raise NotOnRosterError(drop_id)

        # TODO: determine how to only add a player once they clear waivers
        # if self.on_waivers(add_id):
        #     raise OnWaiversError(f"Player {add_id} is on waivers!")

        while True:
            print(f'The time is {datetime.now()}.')
            if drop_id is not None and not self.is_rostered(drop_id):
                print("Player to drop has already been dropped.")
                return
            try:
                # TODO: break out waiver claims into separate method
                # add_response = self.client.add_player(add_id=add_id, drop_id=drop_id, faab=faab)
                add_response = self.client.add_player(add_id=add_id, drop_id=drop_id)
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
            except FantasyUnknownError as err:
                print(f'Error:{err}\nSleeping 0.1 seconds.')
                sleep(0.1)
                continue

    def edit_lineup(self, roster_filename: str, game_date: date):
        data = {
            'ret': 'swap',
            'date': datetime.strftime(game_date, '%Y-%m-%d'),
            'stat1': 'S',
            'stat2': 'D',
            'crumb': self.config.get_crumb(self.league.platform),
        }
        roster_data = self.config.get_roster_data(self.league.name_abbr)
        data.update(roster_data)
        return self.session.post(f'{self.team_url}/editroster', data=data)
