#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python

"""Make a change to your roster.

Usage:
  update_roster.py waivers --league=<league_id> --locked=<locked_players> --add=<player_id> [--drop=<player_id>]
  update_roster.py lineup --league=<league_id> --locked=<locked_players> --roster-file=<path_to_roster_file>
  update_roster.py check --league=<league_id> --locked=<locked_players> --check=<players_to_check>

Options:
  --drop=<player_id>    Id of player to drop.

"""

import os
import json
import requests
import yaml
from datetime import datetime
from pathlib import Path
from typing import List

from docopt import docopt

from headers import COOKIE, CRUMB


YAHOO_FANTASY_URL = 'https://hockey.fantasysports.yahoo.com/hockey'
PROJECT_DIR = Path(__file__).parent.absolute()

class RosterController:
    
    def __init__(self, league_id: str, locked_players: List):
        self.team_url = f'{YAHOO_FANTASY_URL}/{league_id}/1'
        self.locked_players = locked_players
        self.rosters_dir = PROJECT_DIR / 'rosters'

        self.session = requests.Session()
        self.session.headers.update({ 'cookie': COOKIE })

    def check_current_auth(self):
        resp = self.session.get(self.team_url)
        if not all (player in resp.text for player in self.locked_players):
            raise RuntimeError('Not logged in!')
    
    def on_roster(self, player_id):
        team_response = self.session.get(self.team_url)
        return f"players/{player_id}" in team_response.text

    def on_waivers(self, player_id):
        add_response = self.session.get(f"{self.team_url}/addplayer?apid={player_id}")
        return "Claim Player From Waivers" in add_response.text

    def add_player(self, add_id: str, drop_id: str = None):
        if self.on_roster(add_player_id):
            print("Already added player!")
            return
        if self.on_waivers(add_id):
            raise RuntimeError(f"Player {add_id} is on waivers!")
        data = {
            'stage': '3',
            'crumb': CRUMB,
            'stat1': 'S',
            'stat2': 'D',
            'apid': add_id,
        }
        if drop_id is not None:
            data['dpid'] = drop_id
        add_response = self.session.post(f'{self.team_url}/addplayer?apid={add_id}', data=data)
        if "player has already played and is no longer" in add_response.text:
            raise ValueError("Player to drop has played today - try tomorrow!")
        if "You have reached the weekly limit" in add_response.text:
            raise RuntimeError("Already reached max adds for the week!")
        if not self.on_roster(add_player_id):
            raise RuntimeError(f"Something went wrong - player {add_id} was not added to roster!  Check CRUMB value.")
        return add_response

    def edit_lineup(self, roster_filename: str):
        data = {
            "date": datetime.strftime(datetime.now(), '%Y-%m-%d'),
            "stat1": "S",
            "stat2": "D",
            'crumb': f'{CRUMB}',
            "ret": "swap"
        }
        with open(self.rosters_dir / f'{roster_filename}.yml') as roster_file:
            roster = yaml.safe_load(roster_file)
        data.update(roster)
        return self.session.post(f'{self.team_url}/editroster', data=data)


if __name__ == '__main__':
    args = docopt(__doc__)
    league_id = args['--league']
    locked_players = args['--locked'].split(',')

    controller = RosterController(league_id, locked_players)
    controller.check_current_auth()

    if args['check']:
        players_to_check = args['--check'].split(',')
        for player in players_to_check:
            if not controller.on_roster(player):
                raise RuntimeError(f"Player '{player}' has not been added!")
        print(f'All players on roster - {players_to_check}')
    if args['lineup']:
        resp = controller.edit_lineup(args['--roster-file'])
    if args['waivers']:
        add_player_id = args['--add']
        controller.add_player(add_player_id, args['--drop'])
        
