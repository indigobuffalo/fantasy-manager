#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python

"""Make a change to your roster.

Usage:
  update_roster.py waivers --league=<league_name> --add=<player_id> [--drop=<player_id>] [--start=<start_date>]
  update_roster.py lineup --league=<league_name> [--roster-file=<path_to_roster_file>] [--start=<start_date>] [--end=<end_date>]
  update_roster.py check --league=<league_name> --check=<players_to_check>

Options:
  --drop=<player_id>    Id of player to drop.

"""
from time import sleep

import re
import requests
import yaml
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List

from docopt import docopt

from headers import COOKIE, CRUMB
from util.time import date_range, current_season_years, num_days_until, upcoming_midnight, sleep_until
from util.exceptions import AlreadyAddedError, AlreadyPlayedError, MaxAddsError, FantasyAuthError, OnWaiversError, \
    FantasyUnknownError, YahooFantasyError, InvalidLeagueError, NotOnRosterError, UnintendedWaiverAddError

YAHOO_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com/hockey'
PROJECT_DIR = Path(__file__).parent.absolute()

ALREADY_PLAYED_MESSAGE = 'player has already played and is no longer'
WEEKLY_LIMIT_MESSAGE = 'You have reached the weekly limit'
WAIVER_CLAIM_PLACED = 'created%2520a%2520waiver%2520claim%2520for'

LEAGUES = {
    # Puckin' Around
    "pa": {
        "league_id": "31175",
        "team_id": 1,
        "locked_players": ["6744", "6751", "6877"] # Eichel, Meier, Kaprizov
        },
    # KKUPFL
    "kkupfl": {
        "league_id": "88127",
        "team_id": 7,
        "locked_players": ["5425", "6758", "8290"] # Kucherov, Barzal, Boldy
    }
}


def get_league_id(leage_name: str) -> int:
    if leage_name not in LEAGUES:
        raise InvalidLeagueError(league_id)
    return LEAGUES[leage_name]["league_id"]


def get_team_id(leage_name: str) -> int:
    if leage_name not in LEAGUES:
        raise InvalidLeagueError(league_id)
    return LEAGUES[leage_name]["team_id"]


def get_locked_player_ids(leage_name: str) -> list[int]:
    if leage_name not in LEAGUES:
        raise InvalidLeagueError(league_id)
    return LEAGUES[leage_name]["locked_players"]

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
    
    def __init__(self, league_id: str, league_number: int, locked_players: List):
        self.team_url = f'{YAHOO_FANTASY_URL}/{league_id}/{league_number}'
        self.locked_players = locked_players

        yr_one, yr_two = current_season_years()
        self.rosters_dir = PROJECT_DIR / 'data' / 'rosters' / f"{yr_one}-{yr_two}" / league_id

        self.session = requests.Session()
        self.session.headers.update({'cookie': COOKIE})

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all(player in resp.text for player in self.locked_players):
            raise FantasyAuthError('Not logged in!')
    
    def on_roster(self, player_id):
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
        if not self.on_roster(add_id):
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

    def add_player(self, add_id: str, add_datetime: datetime, drop_id: str = None):
        print(f"Adding {get_player_name(add_id)} and dropping {get_player_name(drop_id)}")
        if self.on_roster(add_player_id):
            raise AlreadyAddedError(add_id)
        if drop_id is not None and not self.on_roster(drop_id):
            raise NotOnRosterError(drop_id)
        # TODO: determine how to handle waivers
        # if self.on_waivers(add_id):
        #     raise OnWaiversError(f"Player {add_id} is on waivers!")

        # NEED TO ALLOW REDIRECTS?
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            'stage': '3',
            'crumb': CRUMB,
            'stat1': 'P',
            'stat2': 'P',
            'apid': add_id,
        }
        if drop_id is not None:
            data['dpid'] = drop_id

        sleep_until(add_datetime)
        while True:
            print(f'The time is {datetime.now()}.')
            if drop_id is not None and not self.on_roster(drop_id):
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


if __name__ == '__main__':
    args = docopt(__doc__)
    league_name = args['--league']
    league_id = get_league_id(league_name)
    league_number = get_team_id(league_name)
    locked_players = get_locked_player_ids(league_name)

    controller = RosterController(league_id, league_number, locked_players)
    controller.check_current_auth()

    print(f"Transaction for league: '{league_name.upper()}'")
    if args['check']:
        players_to_check = args['--check'].split(',')
        for player in players_to_check:
            if not controller.on_roster(player):
                raise RuntimeError(f"Player '{player}' has not been added!")
        print(f'All players on roster - {players_to_check}')

    if args['lineup']:
        start, end = args['--start'], args['--end']

        if start is not None:
            start_date = datetime.strptime(start, '%Y-%m-%d')
        else:
            start_date = date.today() + timedelta(days=1)
        if end is not None:
            end_date = datetime.strptime(end, '%Y-%m-%d')
        else:
            days_until_sunday = num_days_until("Sunday", start_date)
            end_date = start_date + timedelta(days=days_until_sunday)

        roster_file = args['--roster-file'] if args['--roster-file'] else 'default.yml'
        for game_date in date_range(start_date, end_date):
            resp = controller.edit_lineup(roster_file, game_date)

    if args['waivers']:
        start = args['--start']
        add_player_id = args['--add']
        add_datetime = datetime.fromisoformat(start) if start else upcoming_midnight()
        try:
            controller.add_player(add_player_id, add_datetime, args['--drop'])
        except AlreadyAddedError:
            print(f"Player '{add_player_id}' is on roster, all set!")
            pass
