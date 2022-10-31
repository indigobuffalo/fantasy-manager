#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python

"""Make a change to your roster.

Usage:
  update_roster.py waivers --league-id=<league_id> --league-number=<league_number>
      --locked=<locked_players> --add=<player_id> [--drop=<player_id>] [--start=<start_date>]
  update_roster.py lineup --league-id=<league_id> --league-number=<league_number> --locked=<locked_players> [--roster-file=<path_to_roster_file>] [--start=<start_date>] [--end=<end_date>]
  update_roster.py check --league-id=<league_id> --league-number=<league_number> --locked=<locked_players> --check=<players_to_check>

Options:
  --drop=<player_id>    Id of player to drop.

"""
from time import sleep

import requests
import yaml
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List

from docopt import docopt

from headers import COOKIE, CRUMB
from util.dates import date_range, current_season_years, num_days_until
from util.exceptions import AlreadyAddedError, AlreadyPlayedError, MaxAddsError, FantasyAuthError, OnWaiversError, \
    FantasyUnknownError, YahooFantasyError

YAHOO_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com/hockey'
PROJECT_DIR = Path(__file__).parent.absolute()

ALREADY_PLAYED_MESSAGE = 'player has already played and is no longer'
WEEKLY_LIMIT_MESSAGE = 'You have reached the weekly limit'


class RosterController:
    
    def __init__(self, league_id: str, league_number: str, locked_players: List):
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
        team_response = self.session.get(self.team_url)
        return f"players/{player_id}" in team_response.text

    # TODO: FIX THIS on_waivers method
    def on_waivers(self, player_id):
        add_response = self.session.get(f"{self.team_url}/addplayer?apid={player_id}")
        return "Claim Player From Waivers" in add_response.text

    def _check_add_response(self, add_id, resp):
        if ALREADY_PLAYED_MESSAGE in resp.text:
            raise AlreadyPlayedError(add_id)
        if WEEKLY_LIMIT_MESSAGE in resp.text:
            raise MaxAddsError("Already reached max adds for the week!")
        if not self.on_roster(add_id):
            raise FantasyUnknownError(f"Error - player '{add_id}' not added.")

    def add_player(self, add_id: str, add_date: date, drop_id: str = None):
        if self.on_roster(add_player_id):
            raise AlreadyAddedError(add_id)
        if self.on_waivers(add_id):
            raise OnWaiversError(f"Player {add_id} is on waivers!")

        data = {
            'stage': '3',
            'crumb': CRUMB,
            'stat1': 'S',
            'stat2': 'D',
            'apid': add_id,
        }
        if drop_id is not None:
            data['dpid'] = drop_id

        midnight = datetime.combine(add_date, datetime.strptime('00:00', '%H:%M').time())
        while True:
            if datetime.now() < midnight:
                seconds_until_midnight = (midnight - datetime.now()).seconds
                minutes_until_midnight = seconds_until_midnight / 60

                if minutes_until_midnight >= 30:
                    print(f"There are '{minutes_until_midnight}' minutes until midnight.  Sleeping 15 minutes.")
                    sleep(900)
                    continue
                elif minutes_until_midnight >= 10:
                    print(f"There are '{minutes_until_midnight}' minutes until midnight.  Sleeping 5 minutes.")
                    sleep(300)
                    continue
                elif minutes_until_midnight >= 2:
                    print(f"There are '{minutes_until_midnight}' minutes until midnight.  Sleeping 1 minutes.")
                    sleep(60)
                    continue
                elif minutes_until_midnight > 1:
                    sleep(15)
                    continue
                elif minutes_until_midnight > 0:
                    if seconds_until_midnight > 45:
                        print(f"There are '{seconds_until_midnight}' seconds until midnight.  Sleeping 5 seconds.")
                        sleep(5)
                        continue
                    elif seconds_until_midnight > 5:
                        print(f"There are '{seconds_until_midnight}' seconds until midnight.  Sleeping 1 second.")
                        sleep(1)
                        continue
                    elif seconds_until_midnight >= 1.5:
                        print(f"There are '{seconds_until_midnight}' seconds until midnight.  Sleeping 0.5 second.")
                        sleep(0.5)
                        continue
                    else:
                        sleep(0.2)
                        continue
            try:
                add_response = self.session.post(f'{self.team_url}/addplayer?apid={add_id}', data=data)
                self._check_add_response(add_id, add_response)
                return add_response
            except YahooFantasyError as err:
                sleep(0.1)
                print(f'The time is {datetime.now()}')
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
    league_id = args['--league-id']
    league_number = args['--league-number']
    locked_players = args['--locked'].split(',')

    controller = RosterController(league_id, league_number, locked_players)
    controller.check_current_auth()

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

        roster_file = args['--roster-file'] if args['--roster-file'] is not None else 'roster.yml'
        for game_date in date_range(start_date, end_date):
            resp = controller.edit_lineup(roster_file, game_date)

    if args['waivers']:
        start = args['--start']

        if start is not None:
            add_date = datetime.strptime(start, '%Y-%m-%d')
        else:
            add_date = date.today() + timedelta(days=1)

        try:
            add_player_id = args['--add']
            controller.add_player(add_player_id, add_date, args['--drop'])
        except AlreadyAddedError:
            print(f"Player '{add_player_id}' is on roster, all set!")
            pass
